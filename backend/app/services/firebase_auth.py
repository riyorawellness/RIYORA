"""Firebase Authentication service.

Wraps the Firebase Admin SDK for verifying ID tokens issued by the frontend
after Google Sign-In or Email/Password authentication. This is our single
authoritative source for asserting "who is this user?" — the backend NEVER
trusts a bare Firebase UID or email sent from the client.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials
from firebase_admin.exceptions import FirebaseError

logger = logging.getLogger(__name__)

_INITIALISED = False


def _init() -> None:
    """Idempotent init — safe to call from multiple places."""
    global _INITIALISED
    if _INITIALISED or firebase_admin._apps:  # noqa: SLF001
        _INITIALISED = True
        return
    cred_path = os.environ.get("FIREBASE_ADMIN_CREDENTIALS_PATH")
    if not cred_path or not os.path.exists(cred_path):
        raise RuntimeError(
            f"Firebase credentials file missing at FIREBASE_ADMIN_CREDENTIALS_PATH='{cred_path}'"
        )
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    _INITIALISED = True
    logger.info("[Firebase] Admin SDK initialised for project=%s", os.environ.get("FIREBASE_PROJECT_ID"))


def verify_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Firebase ID token issued by the frontend.

    Returns the decoded token dict on success. Raises ValueError on any
    tampering / expiry / bad signature. Callers should convert to a 401.
    """
    _init()
    if not id_token or not isinstance(id_token, str):
        raise ValueError("id_token missing")
    try:
        # check_revoked=True → forces a Firebase Admin refresh if the user
        # was disabled or their tokens were revoked out-of-band.
        decoded = fb_auth.verify_id_token(id_token, check_revoked=True)
    except fb_auth.RevokedIdTokenError as exc:
        raise ValueError("Firebase token revoked. Please sign in again.") from exc
    except fb_auth.ExpiredIdTokenError as exc:
        raise ValueError("Firebase token expired. Please sign in again.") from exc
    except fb_auth.UserDisabledError as exc:
        raise ValueError("Firebase account disabled.") from exc
    except fb_auth.InvalidIdTokenError as exc:
        raise ValueError(f"Invalid Firebase token: {exc}") from exc
    except FirebaseError as exc:
        raise ValueError(f"Firebase verification failed: {exc}") from exc

    # Minimum required fields.
    if not decoded.get("uid"):
        raise ValueError("Firebase token missing uid")
    return decoded


def summarise(decoded: dict) -> dict:
    """Extract only the fields we care about from a decoded token."""
    firebase_data = decoded.get("firebase") or {}
    provider = (firebase_data.get("sign_in_provider") or "").lower()
    # Normalise provider → 'google' | 'email' | 'other'
    if provider == "google.com":
        method = "google"
    elif provider == "password":
        method = "email"
    else:
        method = provider or "other"
    return {
        "uid": decoded["uid"],
        "email": (decoded.get("email") or "").lower().strip() or None,
        "email_verified": bool(decoded.get("email_verified", False)),
        "name": decoded.get("name") or None,
        "picture": decoded.get("picture") or None,
        "provider": provider,
        "login_method": method,
    }


def get_user(uid: str) -> dict | None:
    """Fetch the Firebase user record for management (disable / delete) uses."""
    _init()
    try:
        u = fb_auth.get_user(uid)
    except fb_auth.UserNotFoundError:
        return None
    return {
        "uid": u.uid,
        "email": u.email,
        "email_verified": u.email_verified,
        "display_name": u.display_name,
        "photo_url": u.photo_url,
        "disabled": u.disabled,
        "provider_ids": [p.provider_id for p in u.provider_data],
    }
