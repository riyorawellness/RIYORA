"""User authentication routes: OTP, register, login, refresh, logout, forgot/reset."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.deps import db, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.schemas import (
    LoginRequest,
    MessageResponse,
    OtpSentResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendOtpRequest,
    TokenPair,
    UserPublic,
    VerifyOtpRequest,
)
from app.utils.audit import log_action
from app.core.security_mw import check_lockout, record_failed_login, reset_lockout
from app.utils.membership import generate_membership_id
from app.utils.otp import (
    PURPOSE_FORGOT,
    PURPOSE_REGISTER,
    consume_verified_otp,
    send_otp,
    verify_otp,
)
from app.utils.serializers import user_to_public

router = APIRouter(prefix="/auth", tags=["Auth"])
settings = get_settings()


async def _issue_tokens(database: AsyncIOMotorDatabase, subject: str, role: str) -> TokenPair:
    jti = str(uuid.uuid4())
    access = create_access_token(subject=subject, role=role)
    refresh = create_refresh_token(subject=subject, role=role, jti=jti)
    now = datetime.now(timezone.utc)
    await database.refresh_tokens.insert_one(
        {
            "jti": jti,
            "user_id": subject,
            "role": role,
            "expires_at": (now + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)).isoformat(),
            "revoked": False,
            "created_at": now.isoformat(),
        }
    )
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/send-otp", response_model=OtpSentResponse)
async def send_otp_endpoint(body: SendOtpRequest, database: AsyncIOMotorDatabase = Depends(db)):
    # For "register": ensure mobile not already taken.
    if body.purpose == PURPOSE_REGISTER:
        existing = await database.users.find_one({"mobile": body.mobile, "deleted_at": None})
        if existing:
            raise HTTPException(status_code=409, detail="Mobile already registered")
    if body.purpose == PURPOSE_FORGOT:
        existing = await database.users.find_one({"mobile": body.mobile, "deleted_at": None})
        if not existing:
            raise HTTPException(status_code=404, detail="No account with this mobile number")

    result = await send_otp(database, body.mobile, body.purpose)
    if not result["ok"]:
        raise HTTPException(status_code=429, detail=result["error"])
    return OtpSentResponse(
        message="OTP sent successfully",
        expires_in_seconds=result["expires_in_seconds"],
        dev_code=result.get("dev_code"),
    )


@router.post("/verify-otp", response_model=MessageResponse)
async def verify_otp_endpoint(body: VerifyOtpRequest, database: AsyncIOMotorDatabase = Depends(db)):
    ok = await verify_otp(database, body.mobile, body.purpose, body.code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    return MessageResponse(message="OTP verified")


@router.post("/register", response_model=dict)
async def register(body: RegisterRequest, database: AsyncIOMotorDatabase = Depends(db)):
    # 1. OTP must be verified for this mobile.
    ok = await consume_verified_otp(database, body.mobile, PURPOSE_REGISTER)
    if not ok:
        raise HTTPException(status_code=400, detail="Mobile OTP not verified. Please verify OTP first.")

    # 2. Mobile uniqueness (race-safe check).
    if await database.users.find_one({"mobile": body.mobile, "deleted_at": None}):
        raise HTTPException(status_code=409, detail="Mobile already registered")

    # 3. Referral ID must exist in memberships (either company or user).
    sponsor = await database.memberships.find_one({"membership_id": body.referral_id, "deleted_at": None})
    if not sponsor:
        raise HTTPException(status_code=400, detail="Invalid Referral ID")

    # 4. Generate a unique membership id.
    membership_id = await generate_membership_id(database)

    now = datetime.now(timezone.utc).isoformat()
    user_doc = {
        "full_name": body.full_name,
        "mobile": body.mobile,
        "state": body.state,
        "city": body.city,
        "password_hash": hash_password(body.password),
        "role": "user",
        "membership_id": membership_id,
        "sponsor_membership_id": sponsor["membership_id"],
        "sponsor_name": sponsor.get("owner_name"),
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    result = await database.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    # 5. Register into memberships (referral tree).
    await database.memberships.insert_one(
        {
            "membership_id": membership_id,
            "owner_name": body.full_name,
            "user_id": str(result.inserted_id),
            "sponsor_membership_id": sponsor["membership_id"],
            "is_company": False,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )

    # 5b. Materialise into referral_tree with computed depth level from root.
    sponsor_tree = await database.referral_tree.find_one(
        {"user_membership_id": sponsor["membership_id"]}
    )
    depth = (sponsor_tree.get("level", 0) if sponsor_tree else 0) + 1
    await database.referral_tree.insert_one(
        {
            "user_membership_id": membership_id,
            "sponsor_membership_id": sponsor["membership_id"],
            "level": depth,
            "joining_date": now,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )

    # 5c. Create empty profile document.
    await database.profiles.insert_one(
        {
            "user_membership_id": membership_id,
            "email": None,
            "dob": None,
            "gender": None,
            "address": None,
            "profile_photo_url": None,
            "occupation": None,
            "alt_contact": None,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )

    # 6. Audit log
    await log_action(database, actor_id=membership_id, action="register", entity="user", entity_id=membership_id)

    # 7. Issue tokens.
    tokens = await _issue_tokens(database, subject=membership_id, role="user")

    return {"user": user_to_public(user_doc), "tokens": tokens.model_dump()}


@router.post("/login", response_model=dict)
async def login(body: LoginRequest, database: AsyncIOMotorDatabase = Depends(db)):
    await check_lockout(database, body.mobile, "user")
    user = await database.users.find_one({"mobile": body.mobile, "deleted_at": None})
    if not user or not verify_password(body.password, user["password_hash"]):
        await record_failed_login(database, body.mobile, "user")
        raise HTTPException(status_code=401, detail="Invalid mobile or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive")
    await reset_lockout(database, body.mobile, "user")
    tokens = await _issue_tokens(database, subject=user["membership_id"], role="user")
    await log_action(database, actor_id=user["membership_id"], action="login", entity="user")
    return {"user": user_to_public(user), "tokens": tokens.model_dump()}


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, database: AsyncIOMotorDatabase = Depends(db)):
    try:
        payload = decode_token(body.refresh_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from e
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    stored = await database.refresh_tokens.find_one({"jti": payload["jti"]})
    if not stored or stored.get("revoked"):
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    subject = payload["sub"]
    role = payload["role"]
    # Rotate: revoke old, issue new pair.
    await database.refresh_tokens.update_one({"jti": payload["jti"]}, {"$set": {"revoked": True}})
    return await _issue_tokens(database, subject=subject, role=role)


@router.post("/logout", response_model=MessageResponse)
async def logout(body: RefreshRequest, database: AsyncIOMotorDatabase = Depends(db)):
    try:
        payload = decode_token(body.refresh_token)
        await database.refresh_tokens.update_one({"jti": payload.get("jti")}, {"$set": {"revoked": True}})
    except Exception:
        pass
    return MessageResponse(message="Logged out")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, database: AsyncIOMotorDatabase = Depends(db)):
    ok = await consume_verified_otp(database, body.mobile, PURPOSE_FORGOT)
    if not ok:
        raise HTTPException(status_code=400, detail="Mobile OTP not verified")
    user = await database.users.find_one({"mobile": body.mobile, "deleted_at": None})
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    await database.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Revoke all refresh tokens for security.
    await database.refresh_tokens.update_many({"user_id": user["membership_id"]}, {"$set": {"revoked": True}})
    await log_action(database, actor_id=user["membership_id"], action="reset_password", entity="user")
    return MessageResponse(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
async def me(current: dict = Depends(get_current_user)):
    return user_to_public(current)
