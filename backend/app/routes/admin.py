"""Admin authentication and profile routes."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.deps import db, get_current_admin
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.schemas import (
    AdminPublic,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SendOtpRequest,
    TokenPair,
    VerifyOtpRequest,
)
from app.utils.audit import log_action
from app.core.security_mw import check_lockout, record_failed_login, reset_lockout
from app.utils.otp import PURPOSE_FORGOT, consume_verified_otp, send_otp, verify_otp
from app.utils.serializers import admin_to_public

router = APIRouter(prefix="/admin", tags=["Admin"])
settings = get_settings()


async def _issue_admin_tokens(database: AsyncIOMotorDatabase, mobile: str) -> TokenPair:
    jti = str(uuid.uuid4())
    access = create_access_token(subject=mobile, role="admin")
    refresh = create_refresh_token(subject=mobile, role="admin", jti=jti)
    now = datetime.now(timezone.utc)
    await database.refresh_tokens.insert_one(
        {
            "jti": jti,
            "user_id": mobile,
            "role": "admin",
            "expires_at": (now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)).isoformat(),
            "revoked": False,
            "created_at": now.isoformat(),
        }
    )
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=dict)
async def admin_login(body: LoginRequest, database: AsyncIOMotorDatabase = Depends(db)):
    await check_lockout(database, body.mobile, "admin")
    admin = await database.admins.find_one({"mobile": body.mobile, "deleted_at": None})
    if not admin or not verify_password(body.password, admin["password_hash"]):
        await record_failed_login(database, body.mobile, "admin")
        raise HTTPException(status_code=401, detail="Invalid mobile or password")
    await reset_lockout(database, body.mobile, "admin")
    tokens = await _issue_admin_tokens(database, admin["mobile"])
    await log_action(database, actor_id=admin["mobile"], action="admin_login", entity="admin")
    return {"admin": admin_to_public(admin), "tokens": tokens.model_dump()}


@router.post("/send-otp", response_model=dict)
async def admin_send_otp(body: SendOtpRequest, database: AsyncIOMotorDatabase = Depends(db)):
    if body.purpose != "forgot_password":
        raise HTTPException(status_code=400, detail="Only forgot_password OTP supported for admin")
    if not await database.admins.find_one({"mobile": body.mobile, "deleted_at": None}):
        raise HTTPException(status_code=404, detail="Admin not found")
    result = await send_otp(database, body.mobile, PURPOSE_FORGOT)
    if not result["ok"]:
        raise HTTPException(status_code=429, detail=result["error"])
    return {"message": "OTP sent", "expires_in_seconds": result["expires_in_seconds"], "dev_code": result.get("dev_code")}


@router.post("/verify-otp", response_model=MessageResponse)
async def admin_verify_otp(body: VerifyOtpRequest, database: AsyncIOMotorDatabase = Depends(db)):
    ok = await verify_otp(database, body.mobile, body.purpose, body.code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    return MessageResponse(message="OTP verified")


@router.post("/reset-password", response_model=MessageResponse)
async def admin_reset_password(body: ResetPasswordRequest, database: AsyncIOMotorDatabase = Depends(db)):
    ok = await consume_verified_otp(database, body.mobile, PURPOSE_FORGOT)
    if not ok:
        raise HTTPException(status_code=400, detail="Mobile OTP not verified")
    admin = await database.admins.find_one({"mobile": body.mobile, "deleted_at": None})
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    await database.admins.update_one(
        {"_id": admin["_id"]},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await database.refresh_tokens.update_many({"user_id": body.mobile, "role": "admin"}, {"$set": {"revoked": True}})
    return MessageResponse(message="Admin password updated")


@router.get("/profile", response_model=AdminPublic)
async def admin_profile(current: dict = Depends(get_current_admin)):
    return admin_to_public(current)


@router.post("/change-password", response_model=MessageResponse)
async def admin_change_password(
    body: dict,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_admin),
):
    """Signed-in admin changes their own password.

    Requires the current password (so a stolen bearer token alone can't
    lock the admin out). All refresh tokens are revoked so every other
    device is signed out.
    """
    old_password = (body.get("old_password") or "").strip()
    new_password = (body.get("new_password") or "").strip()

    if not old_password or not new_password:
        raise HTTPException(status_code=400, detail="Both old_password and new_password are required")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    if new_password == old_password:
        raise HTTPException(status_code=400, detail="New password must differ from the current password")
    if not verify_password(old_password, current["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    now = datetime.now(timezone.utc).isoformat()
    await database.admins.update_one(
        {"_id": current["_id"]},
        {"$set": {"password_hash": hash_password(new_password), "updated_at": now}},
    )
    # Sign out every other session — the admin will need to log in again
    # on other devices with the new password.
    await database.refresh_tokens.update_many(
        {"user_id": current["mobile"], "role": "admin"},
        {"$set": {"revoked": True}},
    )
    await log_action(
        database,
        actor_id=current["mobile"],
        action="admin.change_password",
        entity="admin",
        entity_id=str(current["_id"]),
    )
    return MessageResponse(message="Password changed successfully")


@router.get("/stats", response_model=dict)
async def admin_stats(current: dict = Depends(get_current_admin), database: AsyncIOMotorDatabase = Depends(db)):
    """Legacy quick stats endpoint. Prefer /admin/dashboard/overview (Phase 7)."""
    total_users = await database.users.count_documents({"deleted_at": None})
    active_users = await database.users.count_documents({"deleted_at": None, "is_active": True})
    total_memberships = await database.memberships.count_documents({"deleted_at": None, "is_company": False})
    total_otps = await database.otp_verifications.count_documents({})
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_memberships": total_memberships,
        "total_otps_sent": total_otps,
    }
