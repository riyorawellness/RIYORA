"""Batch 2 — Admin Preview Mode (impersonation + mark-paid) regression."""
import uuid
import os
from pathlib import Path
from tests.helpers.firebase_seed import seed_test_user  # noqa: E402

import pytest
import requests

_env = Path("/app/frontend/.env")
for _ln in _env.read_text().splitlines():
    if _ln.startswith("REACT_APP_BACKEND_URL"):
        os.environ["REACT_APP_BACKEND_URL"] = _ln.split("=", 1)[1].strip().strip('"')

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"
COMPANY_REF = "RW000000"
DEV_OTP = "123456"
DEFAULT_PASSWORD = "Passw0rd!"


def _rand_mobile():
    import random
    return random.choice("6789") + "".join(random.choices("0123456789", k=9))


def _slug(prefix="b2"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register():
    """Seed a dummy user + return a login-shaped dict (post-Firebase migration)."""
    r = seed_test_user(full_name="TEST_User")
    return {
        "mobile": r["mobile"],
        "membership_id": r["membership_id"],
        "password": r["password"],
        "token": r["access_token"],
        "refresh_token": r["refresh_token"],
        "headers": {
            "Authorization": f"Bearer {r['access_token']}",
            "Content-Type": "application/json",
        },
    }


@pytest.fixture(scope="module")
def admin_h():
    r = requests.post(
        f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD}
    )
    return {
        "Authorization": f"Bearer {r.json()['tokens']['access_token']}",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="module")
def cat(admin_h):
    r = requests.post(
        f"{API}/categories/admin",
        headers=admin_h,
        json={"name": "TEST_B2_Cat", "slug": _slug("cat"), "order_index": 985},
    )
    return r.json()


@pytest.fixture(scope="module")
def program(admin_h, cat):
    r = requests.post(
        f"{API}/programs/admin",
        headers=admin_h,
        json={
            "name": f"TEST_B2_{uuid.uuid4().hex[:6]}",
            "slug": _slug("p"),
            "price": 1500,
            "validity_days": 45,
            "gst_percent": 0,
            "category_id": cat["id"],
            "is_subscription": False,
        },
    )
    return r.json()


class TestAdminPreview:
    def test_impersonate_ok(self, admin_h):
        u = _register()
        r = requests.post(
            f"{API}/admin/preview/impersonate/{u['membership_id']}",
            headers=admin_h,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["preview"] is True
        assert d["impersonated_by"] == ADMIN_MOBILE
        assert d["user"]["membership_id"] == u["membership_id"]
        assert d["access_token"]
        assert d["expires_in_minutes"] == 30

    def test_impersonate_company_root_blocked(self, admin_h):
        r = requests.post(
            f"{API}/admin/preview/impersonate/RW000000", headers=admin_h
        )
        assert r.status_code == 403

    def test_impersonate_unknown_user_404(self, admin_h):
        r = requests.post(
            f"{API}/admin/preview/impersonate/RW999999", headers=admin_h
        )
        assert r.status_code == 404

    def test_impersonate_requires_admin(self):
        u = _register()
        r = requests.post(
            f"{API}/admin/preview/impersonate/{u['membership_id']}",
            headers=u["headers"],  # user token, not admin
        )
        assert r.status_code == 403

    def test_mark_paid_grants_access(self, admin_h, program):
        u = _register()
        # Get impersonation token
        imp = requests.post(
            f"{API}/admin/preview/impersonate/{u['membership_id']}",
            headers=admin_h,
        ).json()
        preview_h = {
            "Authorization": f"Bearer {imp['access_token']}",
            "Content-Type": "application/json",
        }
        # Before mark-paid: no access
        st1 = requests.get(f"{API}/programs/{program['id']}/status", headers=preview_h).json()
        assert st1["has_access"] is False

        # Mark as paid
        r = requests.post(
            f"{API}/admin/preview/mark-paid",
            headers=preview_h,
            json={"program_id": program["id"]},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["success"] is True
        assert d["created"] is True
        assert d["purchase"]["source"] == "admin_preview"
        assert d["purchase"]["is_mock"] is True

        # After: has access
        st2 = requests.get(f"{API}/programs/{program['id']}/status", headers=preview_h).json()
        assert st2["has_access"] is True

    def test_mark_paid_idempotent(self, admin_h, program):
        u = _register()
        imp = requests.post(
            f"{API}/admin/preview/impersonate/{u['membership_id']}",
            headers=admin_h,
        ).json()
        preview_h = {
            "Authorization": f"Bearer {imp['access_token']}",
            "Content-Type": "application/json",
        }
        r1 = requests.post(
            f"{API}/admin/preview/mark-paid",
            headers=preview_h,
            json={"program_id": program["id"]},
        )
        assert r1.status_code == 200
        r2 = requests.post(
            f"{API}/admin/preview/mark-paid",
            headers=preview_h,
            json={"program_id": program["id"]},
        )
        assert r2.status_code == 200
        assert r2.json()["created"] is False  # already had access

    def test_mark_paid_requires_impersonation(self, program):
        u = _register()
        # Use real user token, NOT an impersonation one
        r = requests.post(
            f"{API}/admin/preview/mark-paid",
            headers=u["headers"],
            json={"program_id": program["id"]},
        )
        assert r.status_code == 403
        assert "preview" in r.text.lower()

    def test_mark_paid_no_commissions_fired(self, admin_h, program):
        """Preview mark-paid should NOT trigger the commission engine — otherwise
        admins testing the app would pollute the sponsor's ledger."""
        # Register user WITH a sponsor (chained upline)
        sponsor = _register()
        # Sub-user under sponsor
        m = _rand_mobile()
        requests.post(f"{API}/auth/send-otp", json={"mobile": m, "purpose": "register"})
        requests.post(f"{API}/auth/verify-otp", json={"mobile": m, "purpose": "register", "code": DEV_OTP})
        r = requests.post(
            f"{API}/auth/register",
            json={
                "full_name": "TEST_B2_Sub",
                "mobile": m,
                "state": "KA",
                "city": "BLR",
                "referral_id": sponsor["membership_id"],
                "password": DEFAULT_PASSWORD,
                "confirm_password": DEFAULT_PASSWORD,
            },
        )
        sub = r.json()

        imp = requests.post(
            f"{API}/admin/preview/impersonate/{sub['user']['membership_id']}",
            headers=admin_h,
        ).json()
        preview_h = {"Authorization": f"Bearer {imp['access_token']}", "Content-Type": "application/json"}
        requests.post(
            f"{API}/admin/preview/mark-paid",
            headers=preview_h,
            json={"program_id": program["id"]},
        )
        # Sponsor should NOT have any commissions from this preview purchase
        c = requests.get(
            f"{API}/commissions/me?page=1&page_size=100",
            headers=sponsor["headers"],
        ).json()
        preview_commissions = [
            row for row in c.get("items", [])
            if row.get("purchase_id") and row.get("program_id") == program["id"]
        ]
        assert len(preview_commissions) == 0
