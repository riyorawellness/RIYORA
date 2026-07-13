"""Firebase Authentication regression suite.

Covers:
- /auth/firebase/sync returns needs_registration=true for a fresh Firebase user
- /auth/firebase/register creates a RIYORA account + issues tokens
- /auth/firebase/sync (second call) returns the logged-in user
- Duplicate mobile → 409
- Invalid referral → 400
- /auth/firebase/link-existing correctly links a legacy account
- Wrong legacy password → 401
- Already-linked Firebase UID reuse → 409
- Legacy /auth/login is blocked once account has firebase_uid
- Invalid token → 401
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import bcrypt
import firebase_admin
import pytest
import requests
from dotenv import load_dotenv
from firebase_admin import auth as fb_auth
from firebase_admin import credentials
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

from tests.helpers.firebase_seed import ADMIN_PASSWORD, ADMIN_MOBILE, _rand_mobile


API = os.environ.get("API_BASE") or "http://localhost:8001/api"
CRED_PATH = os.environ.get("FIREBASE_ADMIN_CREDENTIALS_PATH", "/app/backend/firebase-admin.json")
WEB_API_KEY = "REDACTED_FIREBASE_WEB_API_KEY"

# Auto-init Admin SDK once for the whole suite.
if not firebase_admin._apps and os.path.exists(CRED_PATH):  # noqa: SLF001
    firebase_admin.initialize_app(credentials.Certificate(CRED_PATH))


def _mint_id_token(uid: str) -> str:
    """Mint a Firebase ID token for a given uid via the Auth REST API."""
    custom = fb_auth.create_custom_token(uid).decode()
    r = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={WEB_API_KEY}",
        json={"token": custom, "returnSecureToken": True},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["idToken"]


def _make_fb_user(email: str | None = None) -> tuple[str, str]:
    """Return (uid, id_token) for a fresh Firebase user; caller cleans up."""
    e = email or f"pytest-{uuid.uuid4().hex[:8]}@riyoratest.example"
    u = fb_auth.create_user(email=e, password="TestPass123!")
    return u.uid, _mint_id_token(u.uid)


def _delete_fb_user(uid: str) -> None:
    try:
        fb_auth.delete_user(uid)
    except Exception:  # noqa: BLE001
        pass


# ----- /auth/firebase/sync ---------------------------------------------------

def test_firebase_sync_rejects_invalid_token():
    r = requests.post(f"{API}/auth/firebase/sync", json={"id_token": "not_a_real_token_abcdefghijk"}, timeout=10)
    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower() or "firebase" in r.json()["detail"].lower()


def test_firebase_sync_first_time_needs_registration():
    uid, tok = _make_fb_user()
    try:
        r = requests.post(f"{API}/auth/firebase/sync", json={"id_token": tok}, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["needs_registration"] is True
        assert body["firebase_user"]["uid"] == uid
        assert body["firebase_user"]["email"]
    finally:
        _delete_fb_user(uid)


# ----- /auth/firebase/register ----------------------------------------------

def test_firebase_register_full_flow():
    uid, tok = _make_fb_user()
    try:
        mobile = _rand_mobile()
        r = requests.post(f"{API}/auth/firebase/register", json={
            "id_token": tok, "mobile": mobile, "referral_id": "RW000000",
            "full_name": "FB Register Test",
        }, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["membership_id"].startswith("RW")
        assert body["user"]["firebase_uid"] == uid
        assert body["user"]["mobile"] == mobile
        assert body["tokens"]["access_token"]

        # sync now returns logged-in user
        r2 = requests.post(f"{API}/auth/firebase/sync", json={"id_token": tok}, timeout=10)
        assert r2.status_code == 200
        assert r2.json()["needs_registration"] is False
        assert r2.json()["user"]["membership_id"] == body["user"]["membership_id"]
    finally:
        _delete_fb_user(uid)


def test_firebase_register_rejects_duplicate_mobile():
    uid1, tok1 = _make_fb_user()
    uid2, tok2 = _make_fb_user()
    try:
        mobile = _rand_mobile()
        r = requests.post(f"{API}/auth/firebase/register", json={
            "id_token": tok1, "mobile": mobile, "referral_id": "RW000000",
            "full_name": "First",
        }, timeout=15)
        assert r.status_code == 200

        r = requests.post(f"{API}/auth/firebase/register", json={
            "id_token": tok2, "mobile": mobile, "referral_id": "RW000000",
            "full_name": "Second",
        }, timeout=15)
        assert r.status_code == 409
        assert "already registered" in r.json()["detail"].lower()
    finally:
        _delete_fb_user(uid1); _delete_fb_user(uid2)


def test_firebase_register_rejects_invalid_referral():
    uid, tok = _make_fb_user()
    try:
        r = requests.post(f"{API}/auth/firebase/register", json={
            "id_token": tok, "mobile": _rand_mobile(),
            "referral_id": "RW999999", "full_name": "Xyz Test",
        }, timeout=10)
        assert r.status_code == 400
        assert "invalid" in r.json()["detail"].lower() or "referral" in r.json()["detail"].lower()
    finally:
        _delete_fb_user(uid)


# ----- /auth/firebase/link-existing -----------------------------------------

def _seed_legacy_user(mobile: str, password: str = "OldPass123!") -> str:
    """Insert a legacy user directly into Mongo (no Firebase link)."""
    mongo = MongoClient(os.environ["MONGO_URL"])
    db_ = mongo[os.environ["DB_NAME"]]
    pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    mid = f"RW{(uuid.uuid4().int % 900000) + 100000}"
    now = datetime.now(timezone.utc).isoformat()
    db_.users.insert_one({
        "full_name": "Legacy", "mobile": mobile, "state": "S", "city": "C",
        "password_hash": pw, "role": "user", "membership_id": mid,
        "sponsor_membership_id": "RW000000", "is_active": True, "is_dummy": False,
        "created_at": now, "updated_at": now, "deleted_at": None,
    })
    db_.memberships.insert_one({
        "membership_id": mid, "owner_name": "Legacy", "sponsor_membership_id": "RW000000",
        "is_company": False, "is_active": True,
        "created_at": now, "updated_at": now, "deleted_at": None,
    })
    return mid


def test_link_existing_happy_path():
    mobile = _rand_mobile()
    mid = _seed_legacy_user(mobile)
    uid, tok = _make_fb_user()
    try:
        r = requests.post(f"{API}/auth/firebase/link-existing", json={
            "id_token": tok, "mobile": mobile, "password": "OldPass123!",
        }, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["user"]["membership_id"] == mid
        assert r.json()["user"]["firebase_uid"] == uid
    finally:
        _delete_fb_user(uid)
        MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].users.delete_one({"membership_id": mid})
        MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].memberships.delete_one({"membership_id": mid})


def test_link_existing_rejects_wrong_password():
    mobile = _rand_mobile()
    mid = _seed_legacy_user(mobile)
    uid, tok = _make_fb_user()
    try:
        r = requests.post(f"{API}/auth/firebase/link-existing", json={
            "id_token": tok, "mobile": mobile, "password": "wrong-password",
        }, timeout=10)
        assert r.status_code == 401
    finally:
        _delete_fb_user(uid)
        MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].users.delete_one({"membership_id": mid})
        MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].memberships.delete_one({"membership_id": mid})


def test_link_existing_blocks_double_link():
    mobile = _rand_mobile()
    mid = _seed_legacy_user(mobile)
    uid1, tok1 = _make_fb_user()
    uid2, tok2 = _make_fb_user()
    try:
        r = requests.post(f"{API}/auth/firebase/link-existing", json={
            "id_token": tok1, "mobile": mobile, "password": "OldPass123!",
        }, timeout=10)
        assert r.status_code == 200
        # Second link attempt with a different Firebase UID must fail.
        r = requests.post(f"{API}/auth/firebase/link-existing", json={
            "id_token": tok2, "mobile": mobile, "password": "OldPass123!",
        }, timeout=10)
        assert r.status_code == 409
    finally:
        _delete_fb_user(uid1); _delete_fb_user(uid2)
        MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].users.delete_one({"membership_id": mid})
        MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].memberships.delete_one({"membership_id": mid})


# ----- Legacy /auth/login blocked for Firebase-linked accounts ---------------

def test_legacy_login_blocked_after_firebase_link():
    mobile = _rand_mobile()
    mid = _seed_legacy_user(mobile)
    uid, tok = _make_fb_user()
    try:
        # First, link.
        r = requests.post(f"{API}/auth/firebase/link-existing", json={
            "id_token": tok, "mobile": mobile, "password": "OldPass123!",
        }, timeout=10)
        assert r.status_code == 200

        # Now legacy login must be blocked (410 Gone).
        r = requests.post(f"{API}/auth/login", json={"mobile": mobile, "password": "OldPass123!"}, timeout=10)
        assert r.status_code == 410
    finally:
        _delete_fb_user(uid)
        MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].users.delete_one({"membership_id": mid})
        MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].memberships.delete_one({"membership_id": mid})


# ----- Removed endpoints must be gone ---------------------------------------

def test_msg91_otp_endpoints_removed():
    for path in ("/auth/send-otp", "/auth/verify-otp", "/auth/register", "/auth/reset-password"):
        r = requests.post(f"{API}{path}", json={}, timeout=5)
        assert r.status_code == 404, f"{path} should be gone but returned {r.status_code}"
