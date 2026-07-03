"""Short-lived content JWT for secure video/audio/PDF streaming.

Issued only after the user has passed all access gates
(program active + not expired + module unlocked). The token embeds the
resource URL + user identity + expiry; `/content/stream/{token}` verifies and
serves. Downloads are blocked at the UI layer (Phase 3) and by content-disposition
headers here.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings

settings = get_settings()

FILE_TOKEN_TYPE = "content"


def issue_content_token(
    user_membership_id: str,
    program_id: str,
    module_id: str,
    resource: str,  # video | audio | pdf
    resource_url: str,
) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    ttl = settings.FILE_TOKEN_TTL_SEC
    payload: dict[str, Any] = {
        "type": FILE_TOKEN_TYPE,
        "sub": user_membership_id,
        "pid": program_id,
        "mid": module_id,
        "res": resource,
        "url": resource_url,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, ttl


def decode_content_token(token: str) -> dict:
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != FILE_TOKEN_TYPE:
        raise ValueError("Invalid token type")
    return payload
