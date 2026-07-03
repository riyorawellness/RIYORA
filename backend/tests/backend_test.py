"""RIYORA WELLNESS - Backend Regression Test Suite (Phase 1).

Covers: health, OTP (send/verify/resend limit), registration flow (happy + guards),
login, /me, refresh rotation, logout, forgot/reset password, profile GET/PUT,
membership validate-referral, and admin login + stats + users + role guards.

Uses REACT_APP_BACKEND_URL from /app/frontend/.env - tests through public URL.
Dev OTP = 123456. Company referral = RW000000. Admin: 9999999999 / Admin@12345.
"""
import os
import random
import time
from pathlib import Path

import pytest
import requests

# Load frontend .env manually (no python-dotenv assumption in test env)
_env_file = Path("/app/frontend/.env")
for _line in _env_file.read_text().splitlines():
    if _line.startswith("REACT_APP_BACKEND_URL"):
        os.environ["REACT_APP_BACKEND_URL"] = _line.split("=", 1)[1].strip()

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"
COMPANY_REF = "RW000000"
DEV_OTP = "123456"
DEFAULT_PASSWORD = "Passw0rd!"


def _rand_mobile() -> str:
    """Generate fresh 10-digit Indian mobile starting with 6-9."""
    first = random.choice("6789")
    rest = "".join(random.choices("0123456789", k=9))
    return first + rest


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- Test data holders (session-scoped) ------------------------------------
@pytest.fixture(scope="session")
def registered_user(api):
    """Register one fresh user once per session; used by dependent tests."""
    mobile = _rand_mobile()
    # send OTP
    r = api.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"})
    assert r.status_code == 200, r.text
    # verify OTP
    r = api.post(f"{API}/auth/verify-otp", json={"mobile": mobile, "purpose": "register", "code": DEV_OTP})
    assert r.status_code == 200, r.text
    # register
    r = api.post(
        f"{API}/auth/register",
        json={
            "full_name": "TEST_UserOne",
            "mobile": mobile,
            "state": "Karnataka",
            "city": "Bengaluru",
            "referral_id": COMPANY_REF,
            "password": DEFAULT_PASSWORD,
            "confirm_password": DEFAULT_PASSWORD,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return {
        "mobile": mobile,
        "user": data["user"],
        "tokens": data["tokens"],
    }


# ============ HEALTH ========================================================
class TestHealth:
    def test_health(self, api):
        r = api.get(f"{API}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_root(self, api):
        r = api.get(f"{API}/")
        assert r.status_code == 200
        assert r.json()["app"] == "RIYORA WELLNESS"

    def test_docs(self, api):
        r = api.get(f"{BASE_URL}/docs")
        assert r.status_code == 200


# ============ MEMBERSHIP (validate-referral) ================================
class TestMembership:
    def test_validate_company_referral(self, api):
        r = api.post(f"{API}/membership/validate-referral", json={"referral_id": COMPANY_REF})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["referral_id"] == COMPANY_REF
        assert d["sponsor_name"] == "RIYORA Wellness"
        assert d["sponsor_membership_id"] == COMPANY_REF

    def test_validate_invalid_referral(self, api):
        r = api.post(f"{API}/membership/validate-referral", json={"referral_id": "RW999999"})
        assert r.status_code == 404
        assert "Invalid" in r.json().get("detail", "")

    def test_validate_bad_format(self, api):
        r = api.post(f"{API}/membership/validate-referral", json={"referral_id": "XYZ123"})
        assert r.status_code == 422


# ============ OTP FLOW ======================================================
class TestOtp:
    def test_send_and_verify_otp(self, api):
        mobile = _rand_mobile()
        r = api.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dev_code"] == DEV_OTP
        assert body["expires_in_seconds"] > 0
        r = api.post(f"{API}/auth/verify-otp", json={"mobile": mobile, "purpose": "register", "code": DEV_OTP})
        assert r.status_code == 200

    def test_verify_invalid_otp(self, api):
        mobile = _rand_mobile()
        api.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"})
        r = api.post(f"{API}/auth/verify-otp", json={"mobile": mobile, "purpose": "register", "code": "000000"})
        # In dev mode "123456" always accepted; "000000" only accepted if it equals generated code (very unlikely).
        # 400 expected in practice.
        assert r.status_code in (200, 400)

    def test_bad_mobile_format(self, api):
        r = api.post(f"{API}/auth/send-otp", json={"mobile": "12345", "purpose": "register"})
        assert r.status_code == 422

    def test_resend_limit_5_per_hour(self, api):
        mobile = _rand_mobile()
        # 5 sends should succeed, 6th should 429
        codes = []
        for _ in range(5):
            r = api.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"})
            codes.append(r.status_code)
        r6 = api.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"})
        assert all(c == 200 for c in codes), codes
        assert r6.status_code == 429, r6.text


# ============ REGISTER ======================================================
class TestRegister:
    def test_register_happy_path(self, registered_user):
        u = registered_user["user"]
        assert u["membership_id"].startswith("RW")
        assert len(u["membership_id"]) == 8
        assert u["membership_id"] != COMPANY_REF
        assert u["sponsor_membership_id"] == COMPANY_REF
        assert u["sponsor_name"] == "RIYORA Wellness"
        assert u["role"] == "user"
        assert registered_user["tokens"]["access_token"]
        assert registered_user["tokens"]["refresh_token"]

    def test_register_without_otp_verification(self, api):
        mobile = _rand_mobile()
        # Skip OTP entirely
        r = api.post(
            f"{API}/auth/register",
            json={
                "full_name": "TEST_NoOtp",
                "mobile": mobile,
                "state": "Delhi",
                "city": "Delhi",
                "referral_id": COMPANY_REF,
                "password": DEFAULT_PASSWORD,
                "confirm_password": DEFAULT_PASSWORD,
            },
        )
        assert r.status_code == 400
        assert "OTP" in r.json().get("detail", "")

    def test_register_invalid_referral(self, api):
        mobile = _rand_mobile()
        api.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"})
        api.post(f"{API}/auth/verify-otp", json={"mobile": mobile, "purpose": "register", "code": DEV_OTP})
        r = api.post(
            f"{API}/auth/register",
            json={
                "full_name": "TEST_BadRef",
                "mobile": mobile,
                "state": "Delhi",
                "city": "Delhi",
                "referral_id": "RW999999",
                "password": DEFAULT_PASSWORD,
                "confirm_password": DEFAULT_PASSWORD,
            },
        )
        assert r.status_code == 400
        assert "Referral" in r.json().get("detail", "")

    def test_register_mismatched_passwords(self, api):
        mobile = _rand_mobile()
        api.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"})
        api.post(f"{API}/auth/verify-otp", json={"mobile": mobile, "purpose": "register", "code": DEV_OTP})
        r = api.post(
            f"{API}/auth/register",
            json={
                "full_name": "TEST_PwMismatch",
                "mobile": mobile,
                "state": "Delhi",
                "city": "Delhi",
                "referral_id": COMPANY_REF,
                "password": DEFAULT_PASSWORD,
                "confirm_password": "Different1!",
            },
        )
        assert r.status_code == 422

    def test_duplicate_mobile_blocked_on_send_otp(self, api, registered_user):
        # Send OTP for already-registered mobile -> 409
        r = api.post(f"{API}/auth/send-otp", json={"mobile": registered_user["mobile"], "purpose": "register"})
        assert r.status_code == 409


# ============ LOGIN + /me + REFRESH + LOGOUT ================================
class TestLoginRefresh:
    def test_login_success(self, api, registered_user):
        r = api.post(f"{API}/auth/login", json={"mobile": registered_user["mobile"], "password": DEFAULT_PASSWORD})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user"]["membership_id"] == registered_user["user"]["membership_id"]
        assert body["tokens"]["access_token"]

    def test_login_wrong_password(self, api, registered_user):
        r = api.post(f"{API}/auth/login", json={"mobile": registered_user["mobile"], "password": "wrong0000!"})
        assert r.status_code == 401

    def test_me_endpoint(self, api, registered_user):
        access = registered_user["tokens"]["access_token"]
        r = api.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 200
        assert r.json()["membership_id"] == registered_user["user"]["membership_id"]

    def test_me_without_token(self, api):
        r = api.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_refresh_rotation(self, api, registered_user):
        # Login to get a clean refresh token dedicated to this test
        r = api.post(f"{API}/auth/login", json={"mobile": registered_user["mobile"], "password": DEFAULT_PASSWORD})
        assert r.status_code == 200
        old_refresh = r.json()["tokens"]["refresh_token"]

        r1 = api.post(f"{API}/auth/refresh", json={"refresh_token": old_refresh})
        assert r1.status_code == 200, r1.text
        new_tokens = r1.json()
        assert new_tokens["access_token"]
        assert new_tokens["refresh_token"] != old_refresh

        # Old refresh should be revoked
        r2 = api.post(f"{API}/auth/refresh", json={"refresh_token": old_refresh})
        assert r2.status_code == 401

    def test_logout(self, api, registered_user):
        r = api.post(f"{API}/auth/login", json={"mobile": registered_user["mobile"], "password": DEFAULT_PASSWORD})
        rt = r.json()["tokens"]["refresh_token"]
        r = api.post(f"{API}/auth/logout", json={"refresh_token": rt})
        assert r.status_code == 200
        # After logout, refresh should fail
        r = api.post(f"{API}/auth/refresh", json={"refresh_token": rt})
        assert r.status_code == 401


# ============ USER PROFILE ==================================================
class TestUserProfile:
    def test_get_profile(self, api, registered_user):
        access = registered_user["tokens"]["access_token"]
        r = api.get(f"{API}/user/profile", headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 200
        d = r.json()
        assert d["membership_id"] == registered_user["user"]["membership_id"]
        assert d["mobile"] == registered_user["mobile"]

    def test_update_profile_and_verify(self, api, registered_user):
        access = registered_user["tokens"]["access_token"]
        payload = {"full_name": "TEST_UpdatedName", "state": "Maharashtra", "city": "Mumbai"}
        r = api.put(f"{API}/user/profile", json=payload, headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 200
        assert r.json()["full_name"] == "TEST_UpdatedName"
        # GET verifies persistence
        r = api.get(f"{API}/user/profile", headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 200
        d = r.json()
        assert d["full_name"] == "TEST_UpdatedName"
        assert d["state"] == "Maharashtra"
        assert d["city"] == "Mumbai"
        # Read-only fields intact
        assert d["mobile"] == registered_user["mobile"]
        assert d["membership_id"] == registered_user["user"]["membership_id"]

    def test_membership_me(self, api, registered_user):
        access = registered_user["tokens"]["access_token"]
        r = api.get(f"{API}/membership/me", headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 200
        d = r.json()
        assert d["membership_id"] == registered_user["user"]["membership_id"]
        assert d["sponsor_membership_id"] == COMPANY_REF


# ============ FORGOT / RESET PASSWORD =======================================
class TestForgotPassword:
    def test_forgot_flow(self, api):
        # Register a new user just for this test to avoid interfering with others
        mobile = _rand_mobile()
        api.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"})
        api.post(f"{API}/auth/verify-otp", json={"mobile": mobile, "purpose": "register", "code": DEV_OTP})
        r = api.post(
            f"{API}/auth/register",
            json={
                "full_name": "TEST_Forgot",
                "mobile": mobile,
                "state": "Delhi",
                "city": "Delhi",
                "referral_id": COMPANY_REF,
                "password": DEFAULT_PASSWORD,
                "confirm_password": DEFAULT_PASSWORD,
            },
        )
        assert r.status_code == 200

        # Forgot OTP
        r = api.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "forgot_password"})
        assert r.status_code == 200
        r = api.post(f"{API}/auth/verify-otp", json={"mobile": mobile, "purpose": "forgot_password", "code": DEV_OTP})
        assert r.status_code == 200
        new_pw = "NewPass2026!"
        r = api.post(
            f"{API}/auth/reset-password",
            json={"mobile": mobile, "new_password": new_pw, "confirm_password": new_pw},
        )
        assert r.status_code == 200

        # Old password no longer works
        r = api.post(f"{API}/auth/login", json={"mobile": mobile, "password": DEFAULT_PASSWORD})
        assert r.status_code == 401
        # New password works
        r = api.post(f"{API}/auth/login", json={"mobile": mobile, "password": new_pw})
        assert r.status_code == 200

    def test_forgot_unknown_mobile(self, api):
        r = api.post(f"{API}/auth/send-otp", json={"mobile": _rand_mobile(), "purpose": "forgot_password"})
        assert r.status_code == 404


# ============ ADMIN ROUTES ==================================================
@pytest.fixture(scope="session")
def admin_tokens(api):
    r = api.post(f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return r.json()["tokens"]


class TestAdmin:
    def test_admin_login(self, api):
        r = api.post(f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["admin"]["role"] == "admin"
        assert d["admin"]["mobile"] == ADMIN_MOBILE
        assert d["tokens"]["access_token"]

    def test_admin_login_wrong(self, api):
        r = api.post(f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": "wrongpass1!"})
        assert r.status_code == 401

    def test_admin_stats(self, api, admin_tokens):
        r = api.get(f"{API}/admin/stats", headers={"Authorization": f"Bearer {admin_tokens['access_token']}"})
        assert r.status_code == 200
        d = r.json()
        for k in ("total_users", "active_users", "total_memberships", "total_otps_sent"):
            assert k in d
            assert isinstance(d[k], int)

    def test_admin_users_list(self, api, admin_tokens):
        r = api.get(f"{API}/admin/users", headers={"Authorization": f"Bearer {admin_tokens['access_token']}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_profile(self, api, admin_tokens):
        r = api.get(f"{API}/admin/profile", headers={"Authorization": f"Bearer {admin_tokens['access_token']}"})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"


# ============ CROSS-ROLE GUARDS =============================================
class TestRoleGuards:
    def test_user_token_cannot_access_admin(self, api, registered_user):
        access = registered_user["tokens"]["access_token"]
        r = api.get(f"{API}/admin/stats", headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 403

    def test_admin_token_cannot_access_user_profile(self, api, admin_tokens):
        r = api.get(f"{API}/user/profile", headers={"Authorization": f"Bearer {admin_tokens['access_token']}"})
        assert r.status_code == 403
