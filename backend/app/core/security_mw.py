"""Security middleware & helpers for Phase 9.

Provides:
    * SecurityHeadersMiddleware — CSP, HSTS, X-Frame, X-Content-Type, Referrer-Policy, Permissions-Policy
    * limiter — slowapi rate-limit singleton (in-memory)
    * check_and_record_login / reset_lockout — brute-force lockout via `login_attempts` collection
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

# ---------- Rate limiter (in-memory) ----------------------------------------

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


# ---------- Security headers -------------------------------------------------

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://checkout.razorpay.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https:; "
        "media-src 'self' blob: https:; "
        "connect-src 'self' https: wss:; "
        "frame-src https://api.razorpay.com https://checkout.razorpay.com; "
        "object-src 'none'; "
        "base-uri 'self'"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response


# ---------- Brute-force lockout ---------------------------------------------

MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


async def check_lockout(db: AsyncIOMotorDatabase, mobile: str, role: str) -> None:
    """Raise 429 if the (mobile, role) is currently locked out."""
    doc = await db.login_attempts.find_one({"mobile": mobile, "role": role})
    if not doc:
        return
    if doc.get("locked_until"):
        try:
            lu = datetime.fromisoformat(doc["locked_until"].replace("Z", "+00:00"))
            if lu > datetime.now(timezone.utc):
                mins = int((lu - datetime.now(timezone.utc)).total_seconds() / 60) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many failed login attempts. Try again in {mins} minute(s).",
                )
        except (ValueError, TypeError):
            pass


async def record_failed_login(db: AsyncIOMotorDatabase, mobile: str, role: str) -> None:
    now = datetime.now(timezone.utc)
    doc = await db.login_attempts.find_one({"mobile": mobile, "role": role})
    attempts = (doc or {}).get("attempts", 0) + 1
    update: dict = {"attempts": attempts, "last_attempt_at": now.isoformat()}
    if attempts >= MAX_ATTEMPTS:
        update["locked_until"] = (now + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
    await db.login_attempts.update_one(
        {"mobile": mobile, "role": role},
        {"$set": update, "$setOnInsert": {"first_attempt_at": now.isoformat()}},
        upsert=True,
    )


async def reset_lockout(db: AsyncIOMotorDatabase, mobile: str, role: str) -> None:
    await db.login_attempts.delete_one({"mobile": mobile, "role": role})
