"""User authentication routes.

MSG91 OTP-based signup, verify-otp, register and reset-password endpoints
have been removed. Firebase authentication routes live in
`app/routes/firebase_auth_routes.py`. This module now retains only:

- POST /auth/login          (legacy mobile+password — kept ONLY for existing
                             users linking their old accounts. New users
                             MUST use Firebase.)
- POST /auth/refresh        (RIYORA JWT rotation, provider-agnostic)
- POST /auth/logout         (revoke a refresh token)
- GET  /auth/me             (current user profile from the RIYORA JWT)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.deps import db, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.core.security_mw import check_lockout, record_failed_login, reset_lockout
from app.models.schemas import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    TokenPair,
    UserPublic,
)
from app.utils.audit import log_action
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


@router.post("/login", response_model=dict, deprecated=True)
async def legacy_login(body: LoginRequest, database: AsyncIOMotorDatabase = Depends(db)):
    """DEPRECATED — legacy mobile+password login for pre-migration users only.

    New sign-ups must use Firebase (`POST /auth/firebase/sync`). This
    endpoint stays alive during the migration window so existing users
    can prove their identity when calling `/auth/firebase/link-existing`.
    Do NOT wire new UI to this route.
    """
    await check_lockout(database, body.mobile, "user")
    user = await database.users.find_one({"mobile": body.mobile, "deleted_at": None})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        await record_failed_login(database, body.mobile, "user")
        raise HTTPException(status_code=401, detail="Invalid mobile or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is inactive")
    if user.get("firebase_uid"):
        # This account has already migrated to Firebase — force them there.
        raise HTTPException(status_code=410, detail="This account now uses Google / Email sign-in. Please sign in with Firebase.")
    await reset_lockout(database, body.mobile, "user")
    tokens = await _issue_tokens(database, subject=user["membership_id"], role="user")
    await log_action(database, actor_id=user["membership_id"], action="login.legacy", entity="user")
    return {"user": user_to_public(user), "tokens": tokens.model_dump()}


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, database: AsyncIOMotorDatabase = Depends(db)):
    try:
        payload = decode_token(body.refresh_token)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid refresh token") from e
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    stored = await database.refresh_tokens.find_one({"jti": payload["jti"]})
    if not stored or stored.get("revoked"):
        raise HTTPException(status_code=401, detail="Refresh token revoked")
    subject = payload["sub"]
    role = payload["role"]
    await database.refresh_tokens.update_one({"jti": payload["jti"]}, {"$set": {"revoked": True}})
    return await _issue_tokens(database, subject=subject, role=role)


@router.post("/logout", response_model=MessageResponse)
async def logout(body: RefreshRequest, database: AsyncIOMotorDatabase = Depends(db)):
    try:
        payload = decode_token(body.refresh_token)
        await database.refresh_tokens.update_one({"jti": payload.get("jti")}, {"$set": {"revoked": True}})
    except Exception:  # noqa: BLE001
        pass
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserPublic)
async def me(current: dict = Depends(get_current_user)):
    return user_to_public(current)
