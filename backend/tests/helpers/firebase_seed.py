"""Shared test helpers for the Firebase migration.

Tests originally used `POST /auth/send-otp` + `/auth/verify-otp` +
`/auth/register` (MSG91-based) to seed users. After migrating to Firebase
those endpoints are gone. This helper offers an equivalent one-shot
seeding path that works against a running server:

    _seed_test_user(...) returns {"membership_id", "mobile", "password",
                                  "access_token", "refresh_token"}

Under the hood we:
1. Log in as the admin (mobile 9999999999 / Admin@12345).
2. Call `POST /admin/users/dummy` — creates a real user account with a
   known mobile + password and no Firebase link (`firebase_uid` = None).
3. Call `POST /auth/login` — the deprecated-but-still-alive legacy
   endpoint which continues to accept mobile+password for accounts that
   have not yet been linked to Firebase.

Tests should import from this module:

    from tests.helpers.firebase_seed import seed_test_user
"""
from __future__ import annotations

import os
import random
import string
import requests

DEFAULT_API_BASE = os.environ.get("API_BASE") or "http://localhost:8001/api"
ADMIN_MOBILE = os.environ.get("ADMIN_MOBILE", "9999999999")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")


def _rand_mobile() -> str:
    return "9" + "".join(random.choices(string.digits, k=9))


def get_admin_token(base: str = DEFAULT_API_BASE) -> str:
    r = requests.post(
        f"{base}/admin/login",
        json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["tokens"]["access_token"]


def seed_test_user(
    full_name: str = "TestUser",
    sponsor: str = "RW000000",
    base: str = DEFAULT_API_BASE,
    mobile: str | None = None,
    password: str = "TestPass1234!",
) -> dict:
    """Create a test user account + return a logged-in token pair.

    The resulting account is marked `is_dummy=True` so its purchases and
    referral events are excluded from revenue analytics — which is exactly
    what integration tests want.
    """
    admin_token = get_admin_token(base)
    m = mobile or _rand_mobile()
    r = requests.post(
        f"{base}/admin/users/dummy",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "full_name": full_name,
            "mobile": m,
            "password": password,
            "sponsor_membership_id": sponsor,
        },
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    membership_id = body["membership_id"]

    # Log the fresh account in via the legacy endpoint (still alive for
    # accounts without a firebase_uid).
    r = requests.post(
        f"{base}/auth/login",
        json={"mobile": m, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    tokens = r.json()["tokens"]

    return {
        "membership_id": membership_id,
        "mobile": m,
        "password": password,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
    }
