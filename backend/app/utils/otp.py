"""OTP generation, storage and verification helpers.

Delivery order:
1. If MSG91 env vars are configured, we attempt to dispatch the OTP via
   MSG91 Flow API. On MSG91 network / API failure we RAISE — the caller
   translates to a 502 for the user so they can retry.
2. If MSG91 is NOT configured (typical for local/dev), we fall back to
   ``OTP_DEV_MODE`` semantics: log the code, optionally echo it back in
   the API response so devs can auto-fill.

Production checklist:
- Set ``MSG91_AUTH_KEY``, ``MSG91_TEMPLATE_ID``, ``MSG91_SENDER_ID`` in .env
- Set ``OTP_DEV_MODE=false`` (removes the dev_code echo and the ``123456``
  master OTP that always verifies)
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.services.sms_msg91 import Msg91Error, is_configured, send_otp_sms

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
    """Create an OTP row for (mobile, purpose). Enforces per-hour resend limit.

    Returns a dict with:
      ok (bool), expires_in_seconds (int|None), dev_code (str|None), error (str|None)
    """
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

    # Try MSG91 dispatch if configured. Otherwise stay in dev/log-only mode.
    msg91_active = is_configured()
    if msg91_active:
        try:
            await send_otp_sms(mobile, code)
        except Msg91Error as exc:
            # Bubble up so the auth route can 502 the client.
            logger.error("[OTP] MSG91 dispatch failed for %s: %s", mobile, exc)
            return {"ok": False, "error": "SMS provider failure. Please try again."}

    logger.info(
        "[OTP] mobile=%s purpose=%s code=%s msg91=%s dev_mode=%s",
        mobile,
        purpose,
        code,
        msg91_active,
        settings.OTP_DEV_MODE,
    )

    # Only echo dev_code when dev mode is ON *and* MSG91 is NOT active. In
    # production (msg91 wired + dev_mode off) the client never sees the code.
    dev_code = None
    if settings.OTP_DEV_MODE and not msg91_active:
        dev_code = settings.OTP_DEV_CODE

    return {
        "ok": True,
        "expires_in_seconds": settings.OTP_TTL_MIN * 60,
        "dev_code": dev_code,
    }


async def verify_otp(db: AsyncIOMotorDatabase, mobile: str, purpose: str, code: str) -> bool:
    """Return True if code is valid & not expired. Marks record verified.

    ``OTP_DEV_CODE`` (default ``123456``) is accepted ONLY when
    ``OTP_DEV_MODE=true`` AND MSG91 is not configured. In production
    (msg91 wired + dev_mode off) the master code is disabled.
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
        return False

    accepted = code == latest["code"]
    if (
        settings.OTP_DEV_MODE
        and not is_configured()
        and code == settings.OTP_DEV_CODE
    ):
        accepted = True

    await db.otp_verifications.update_one(
        {"_id": latest["_id"]},
        {"$inc": {"attempts": 1}, "$set": {"verified": accepted}},
    )
    return accepted


async def consume_verified_otp(db: AsyncIOMotorDatabase, mobile: str, purpose: str) -> bool:
    """Check that the most recent OTP for (mobile, purpose) is verified and unexpired."""
    latest = await db.otp_verifications.find_one(
        {"mobile": mobile, "purpose": purpose},
        sort=[("created_at", -1)],
    )
    if not latest:
        return False
    if not latest.get("verified"):
        return False
    await db.otp_verifications.update_one(
        {"_id": latest["_id"]}, {"$set": {"consumed": True, "verified": False}}
    )
    return True
