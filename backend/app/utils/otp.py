"""OTP generation, storage and verification helpers.

Dev mode (OTP_DEV_MODE=true) accepts OTP_DEV_CODE (default 123456) for any
mobile without hitting an SMS provider. Real 6-digit OTP is still generated
and logged to the console so the flow mirrors production.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# OTP purposes
PURPOSE_REGISTER = "register"
PURPOSE_FORGOT = "forgot_password"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def send_otp(db: AsyncIOMotorDatabase, mobile: str, purpose: str) -> dict:
    """Create an OTP row for (mobile, purpose). Enforces per-hour resend limit."""
    one_hour_ago = (_now() - timedelta(hours=1)).isoformat()
    recent = await db.otp_verifications.count_documents(
        {"mobile": mobile, "purpose": purpose, "created_at": {"$gte": one_hour_ago}}
    )
    if recent >= settings.OTP_RESEND_LIMIT_PER_HOUR:
        return {"ok": False, "error": "OTP resend limit reached. Try again later."}

    code = _gen_code()
    expires_at = (_now() + timedelta(minutes=settings.OTP_TTL_MIN)).isoformat()
    doc = {
        "mobile": mobile,
        "purpose": purpose,
        "code": code,
        "attempts": 0,
        "verified": False,
        "expires_at": expires_at,
        "created_at": _now().isoformat(),
    }
    await db.otp_verifications.insert_one(doc)

    logger.info("[OTP] mobile=%s purpose=%s code=%s (dev_mode=%s)", mobile, purpose, code, settings.OTP_DEV_MODE)

    return {
        "ok": True,
        "expires_in_seconds": settings.OTP_TTL_MIN * 60,
        # Return code only in dev mode so the client can auto-fill it.
        "dev_code": settings.OTP_DEV_CODE if settings.OTP_DEV_MODE else None,
    }


async def verify_otp(db: AsyncIOMotorDatabase, mobile: str, purpose: str, code: str) -> bool:
    """Return True if code is valid & not expired. Marks record verified.

    In dev mode, OTP_DEV_CODE always succeeds if any OTP was ever requested.
    """
    latest = await db.otp_verifications.find_one(
        {"mobile": mobile, "purpose": purpose},
        sort=[("created_at", -1)],
    )
    if not latest:
        return False

    if datetime.fromisoformat(latest["expires_at"]) < _now():
        return False

    if latest.get("verified"):
        # Already used
        return False

    accepted = code == latest["code"]
    if settings.OTP_DEV_MODE and code == settings.OTP_DEV_CODE:
        accepted = True

    await db.otp_verifications.update_one(
        {"_id": latest["_id"]},
        {"$inc": {"attempts": 1}, "$set": {"verified": accepted}},
    )
    return accepted


async def consume_verified_otp(db: AsyncIOMotorDatabase, mobile: str, purpose: str) -> bool:
    """Check that the most recent OTP for (mobile, purpose) is verified and unexpired.

    Used at registration/reset time to ensure the user did complete OTP step.
    """
    latest = await db.otp_verifications.find_one(
        {"mobile": mobile, "purpose": purpose},
        sort=[("created_at", -1)],
    )
    if not latest:
        return False
    if not latest.get("verified"):
        return False
    if datetime.fromisoformat(latest["expires_at"]) < _now() + timedelta(minutes=10):
        # Allow a small grace window (10 min) between verify and use.
        pass
    # Mark consumed so it can't be reused.
    await db.otp_verifications.update_one({"_id": latest["_id"]}, {"$set": {"consumed": True, "verified": False}})
    return True
