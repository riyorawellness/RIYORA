"""Firebase-backed authentication routes.

Flow:
1. Frontend runs Google popup or email/password via Firebase JS SDK.
2. Frontend calls POST /auth/firebase/sync with the resulting Firebase ID
   token.
3. Backend verifies the token via Firebase Admin SDK. Three outcomes:
     a. Firebase UID (or email) matches an existing RIYORA user → we log
        them in and mint a RIYORA JWT.
     b. No RIYORA user yet → we return `needs_registration=true` plus the
        Firebase user summary; the frontend redirects to a "Complete
        RIYORA profile" screen which then calls POST /auth/firebase/register
        with the ID token + mobile + referral_id + optional profile fields.
     c. Legacy RIYORA account exists for the SAME EMAIL as the Firebase
        user (rare edge case: user pre-added email in profile before
        migration) → auto-link and log in.
4. Legacy users (mobile+password, no Firebase account) can either sign up
   from scratch (their old data will collide on mobile) OR use the
   dedicated /auth/firebase/link-existing endpoint which requires proof
   of old-password ownership and grafts their Firebase UID onto the
   existing RIYORA membership without any data loss.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.deps import db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.core.security_mw import check_lockout, record_failed_login, reset_lockout
from app.models.schemas import TokenPair
from app.services import firebase_auth as fb
from app.utils.audit import log_action
from app.utils.membership import generate_membership_id
from app.utils.serializers import user_to_public

router = APIRouter(prefix="/auth/firebase", tags=["Auth · Firebase"])
settings = get_settings()

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")  # Indian 10-digit


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


async def _find_user_by_firebase(database: AsyncIOMotorDatabase, fb_summary: dict) -> dict | None:
    """Look up an existing RIYORA user by (a) firebase_uid then (b) matching
    email — this makes the migration path automatic for users who happen to
    have their email already recorded."""
    if fb_summary.get("uid"):
        u = await database.users.find_one({"firebase_uid": fb_summary["uid"], "deleted_at": None})
        if u:
            return u
    if fb_summary.get("email"):
        u = await database.users.find_one({"email": fb_summary["email"], "deleted_at": None})
        if u:
            return u
    return None


async def _touch_login(database: AsyncIOMotorDatabase, user_doc: dict, fb_summary: dict) -> dict:
    """Update last_login_at + refresh any stale Firebase fields on the user doc."""
    now = datetime.now(timezone.utc).isoformat()
    updates = {"last_login_at": now, "updated_at": now}
    if fb_summary.get("uid") and user_doc.get("firebase_uid") != fb_summary["uid"]:
        updates["firebase_uid"] = fb_summary["uid"]
    if fb_summary.get("email") and user_doc.get("email") != fb_summary["email"]:
        updates["email"] = fb_summary["email"]
    if fb_summary.get("login_method") and user_doc.get("login_method") != fb_summary["login_method"]:
        updates["login_method"] = fb_summary["login_method"]
    if fb_summary.get("email_verified") is not None:
        updates["email_verified"] = fb_summary["email_verified"]
    if fb_summary.get("picture") and not user_doc.get("photo_url"):
        updates["photo_url"] = fb_summary["picture"]
    await database.users.update_one({"_id": user_doc["_id"]}, {"$set": updates})
    user_doc.update(updates)
    return user_doc


# ============================================================================
# Requests / responses
# ============================================================================

class FirebaseTokenBody(BaseModel):
    id_token: str = Field(min_length=10)


class FirebaseRegisterBody(BaseModel):
    id_token: str = Field(min_length=10)
    mobile: str = Field(min_length=10, max_length=10)
    referral_id: str = Field(min_length=8, max_length=8, pattern=r"^RW\d{6}$", description="Sponsor Membership ID — 8 chars: 'RW' + 6 digits.")
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    state: str = Field(default="", max_length=60)
    city: str = Field(default="", max_length=60)
    pincode: str | None = Field(default=None, max_length=10)
    gender: str | None = Field(default=None, max_length=20)
    dob: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=250)


class FirebaseLinkExistingBody(BaseModel):
    id_token: str = Field(min_length=10)
    mobile: str = Field(min_length=10, max_length=10)
    password: str = Field(min_length=1, max_length=128)


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/sync")
async def firebase_sync(body: FirebaseTokenBody, database: AsyncIOMotorDatabase = Depends(db)):
    """Log the user in with a Firebase ID token; if no RIYORA account
    exists yet, tell the frontend to redirect to the completion screen."""
    try:
        decoded = fb.verify_id_token(body.id_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    summary = fb.summarise(decoded)

    user = await _find_user_by_firebase(database, summary)
    if user is None:
        return {
            "needs_registration": True,
            "firebase_user": summary,
        }

    if not user.get("is_active", True):
        raise HTTPException(403, "Account is inactive. Contact support.")

    user = await _touch_login(database, user, summary)
    tokens = await _issue_tokens(database, subject=user["membership_id"], role="user")
    await log_action(database, actor_id=user["membership_id"], action="firebase.login", entity="user",
                     meta={"method": summary["login_method"], "email": summary.get("email")})
    return {
        "needs_registration": False,
        "user": user_to_public(user),
        "tokens": tokens.model_dump(),
    }


@router.post("/register")
async def firebase_register(body: FirebaseRegisterBody, database: AsyncIOMotorDatabase = Depends(db)):
    """Create a new RIYORA account after Firebase auth succeeded on the frontend."""
    try:
        decoded = fb.verify_id_token(body.id_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    summary = fb.summarise(decoded)

    # If this Firebase UID or email already maps to a RIYORA account, they
    # should have gone through /sync — bail with a clear error.
    if await _find_user_by_firebase(database, summary):
        raise HTTPException(409, "This account already exists. Please sign in instead.")

    # Email-verification gate. For password-based signups Firebase sets
    # email_verified=False until the user clicks the link we emailed. We
    # DO NOT create a RIYORA membership until that flips to True; the
    # frontend polls Firebase for the flag and only calls this endpoint
    # once verified.  Google logins arrive already-verified so this passes
    # through without friction.
    if summary.get("login_method") == "email" and not summary.get("email_verified"):
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before creating your RIYORA profile.",
        )

    # Mobile format + uniqueness.
    if not MOBILE_RE.match(body.mobile):
        raise HTTPException(400, "Enter a valid 10-digit Indian mobile number")
    if await database.users.find_one({"mobile": body.mobile, "deleted_at": None}):
        raise HTTPException(409, "This mobile number is already registered.")

    # Referral must exist AND be active (per requirement).
    sponsor = await database.memberships.find_one(
        {"membership_id": body.referral_id, "deleted_at": None}
    )
    if not sponsor or not sponsor.get("is_active", True):
        raise HTTPException(400, "Invalid or inactive Referral ID.")

    membership_id = await generate_membership_id(database)
    now = datetime.now(timezone.utc).isoformat()

    full_name = (body.full_name or summary.get("name") or "").strip()
    if len(full_name) < 2:
        raise HTTPException(400, "Full name is required (min 2 characters).")

    user_doc = {
        "full_name": full_name,
        "mobile": body.mobile,
        "state": body.state or "",
        "city": body.city or "",
        "district": "",
        "pincode": body.pincode or "",
        "address": body.address,
        "gender": body.gender,
        "dob": body.dob,
        "password_hash": None,  # Firebase owns password now
        "role": "user",
        "membership_id": membership_id,
        "sponsor_membership_id": sponsor["membership_id"],
        "sponsor_name": sponsor.get("owner_name"),
        "is_active": True,
        "is_dummy": False,
        "firebase_uid": summary["uid"],
        "email": summary.get("email"),
        "email_verified": summary.get("email_verified", False),
        "login_method": summary.get("login_method"),
        "photo_url": summary.get("picture"),
        "last_login_at": now,
        "joining_date": now,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    result = await database.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    await database.memberships.insert_one(
        {
            "membership_id": membership_id,
            "owner_name": full_name,
            "user_id": str(result.inserted_id),
            "sponsor_membership_id": sponsor["membership_id"],
            "is_company": False,
            "is_active": True,
            "is_dummy": False,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )
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
    await database.profiles.insert_one(
        {
            "user_membership_id": membership_id,
            "email": summary.get("email"),
            "dob": body.dob,
            "gender": body.gender,
            "address": body.address,
            "pincode": body.pincode,
            "profile_photo_url": summary.get("picture"),
            "occupation": None,
            "alt_contact": None,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )
    await log_action(database, actor_id=membership_id, action="firebase.register", entity="user",
                     entity_id=membership_id, meta={"method": summary["login_method"], "email": summary.get("email")})

    tokens = await _issue_tokens(database, subject=membership_id, role="user")
    return {
        "user": user_to_public(user_doc),
        "tokens": tokens.model_dump(),
    }


@router.post("/link-existing")
async def firebase_link_existing(body: FirebaseLinkExistingBody, database: AsyncIOMotorDatabase = Depends(db)):
    """Attach a fresh Firebase account onto an existing legacy RIYORA user.

    Existing legacy users have (mobile, password_hash) but no `firebase_uid`
    yet. They sign up on Firebase (Google or email/password), then send us
    that ID token PLUS their original mobile + password. We verify both
    ends: the Firebase token proves they own the Firebase account, and the
    legacy password proves they own the RIYORA account. Both must succeed
    to link — this prevents anyone from hijacking a stranger's data.
    """
    try:
        decoded = fb.verify_id_token(body.id_token)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    summary = fb.summarise(decoded)

    # Firebase side: refuse if this UID is already linked.
    if await database.users.find_one({"firebase_uid": summary["uid"], "deleted_at": None}):
        raise HTTPException(409, "This Google/Email account is already linked to a RIYORA membership. Sign in instead.")

    # Legacy side: prove ownership of the old mobile+password combo.
    await check_lockout(database, body.mobile, "user")
    legacy = await database.users.find_one({"mobile": body.mobile, "deleted_at": None})
    if not legacy or not legacy.get("password_hash") or not verify_password(body.password, legacy["password_hash"]):
        await record_failed_login(database, body.mobile, "user")
        raise HTTPException(401, "No RIYORA account found for this mobile + password.")
    if legacy.get("firebase_uid"):
        raise HTTPException(409, "This RIYORA account is already linked to a different sign-in method.")
    if not legacy.get("is_active", True):
        raise HTTPException(403, "Account is inactive. Contact support.")
    await reset_lockout(database, body.mobile, "user")

    # If Firebase-side email is already used by another RIYORA user, block.
    if summary.get("email"):
        clash = await database.users.find_one({
            "email": summary["email"],
            "membership_id": {"$ne": legacy["membership_id"]},
            "deleted_at": None,
        })
        if clash:
            raise HTTPException(409, "This email is already linked to another RIYORA account.")

    now = datetime.now(timezone.utc).isoformat()
    updates = {
        "firebase_uid": summary["uid"],
        "email": summary.get("email"),
        "email_verified": summary.get("email_verified", False),
        "login_method": summary.get("login_method"),
        "photo_url": summary.get("picture") or legacy.get("photo_url"),
        "last_login_at": now,
        "updated_at": now,
    }
    await database.users.update_one({"_id": legacy["_id"]}, {"$set": updates})
    legacy.update(updates)

    tokens = await _issue_tokens(database, subject=legacy["membership_id"], role="user")
    await log_action(database, actor_id=legacy["membership_id"], action="firebase.link_existing", entity="user",
                     entity_id=legacy["membership_id"], meta={"method": summary["login_method"], "email": summary.get("email")})
    return {
        "user": user_to_public(legacy),
        "tokens": tokens.model_dump(),
    }
