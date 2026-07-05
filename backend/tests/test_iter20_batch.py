"""Iteration 20 — targeted regression:

1. Banner delete endpoint (behind trash-icon dialog in FE).
2. Granular ``DELETE /api/admin/danger/users/{mid}`` with per-scope booleans
   → correct ``wiped`` dict + only the requested collections purged.
3. Referral-tree safety by default (unchecked → row preserved).
4. Real-time notifications /me/unread-count + no duplication regression.
"""
import os
import random
import string
import uuid

import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"
COMPANY_ID = "RW000000"
DEV_OTP = "123456"


# ---------------------------------------------------------------- helpers
def _rand_mobile() -> str:
    while True:
        prefix = random.choice(["7", "8"])
        rest = "".join(random.choices(string.digits, k=9))
        m = prefix + rest
        if m != ADMIN_MOBILE:
            return m


def _admin_headers() -> dict:
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    tok = r.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _register_user(mobile: str, password: str = "Passw0rd!", referral: str = COMPANY_ID) -> dict:
    r = requests.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"}, timeout=15)
    assert r.status_code == 200, r.text
    r = requests.post(f"{API}/auth/verify-otp",
                      json={"mobile": mobile, "purpose": "register", "code": DEV_OTP}, timeout=15)
    assert r.status_code == 200, r.text
    r = requests.post(
        f"{API}/auth/register",
        json={
            "full_name": f"Test {mobile[-4:]}",
            "mobile": mobile,
            "state": "Delhi",
            "city": "Delhi",
            "password": password,
            "confirm_password": password,
            "referral_id": referral,
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _user_headers(reg: dict) -> dict:
    return {"Authorization": f"Bearer {reg['tokens']['access_token']}", "Content-Type": "application/json"}


# =================================================================== BUG 1
class TestBannerDelete:
    def test_create_then_delete_banner(self):
        h = _admin_headers()
        payload = {
            "title": f"TEST_BANNER_{uuid.uuid4().hex[:6]}",
            "image_url": "https://placehold.co/600x300",
            "cta_label": "", "cta_link": "",
            "placement": "home", "priority": 0,
            "schedule_start": None, "schedule_end": None,
            "is_active": True,
        }
        r = requests.post(f"{API}/admin/banners", json=payload, headers=h, timeout=15)
        assert r.status_code in (200, 201), r.text
        bid = r.json()["id"]

        r = requests.get(f"{API}/admin/banners", headers=h, timeout=15)
        assert r.status_code == 200
        assert any(b["id"] == bid for b in r.json().get("items", []))

        r = requests.delete(f"{API}/admin/banners/{bid}", headers=h, timeout=15)
        assert r.status_code in (200, 204), r.text

        r = requests.get(f"{API}/admin/banners", headers=h, timeout=15)
        assert not any(b["id"] == bid for b in r.json().get("items", []))


# =================================================================== BUG 2: granular delete
class TestGranularDeleteUser:
    def test_only_notifications_scope_wiped(self):
        """Register user + create notification. Delete with ONLY wipe_notifications=True
        and wipe_profile=False → profiles row preserved, notifications purged."""
        h = _admin_headers()

        m = _rand_mobile()
        reg = _register_user(m)
        mid = reg["user"]["membership_id"]

        # Populate a profile so we can prove it survives when wipe_profile=False
        uh = _user_headers(reg)
        r = requests.put(f"{API}/profiles/me", json={"email": f"test_{m[-4:]}@example.com"}, headers=uh, timeout=15)
        assert r.status_code == 200, r.text

        # Send a targeted notification to this user via admin
        r = requests.post(
            f"{API}/admin/notifications",
            json={
                "title": f"TEST_{uuid.uuid4().hex[:6]}",
                "body": "iter20 granular test",
                "category": "system",
                "is_broadcast": False,
                "target_membership_ids": [mid],
            },
            headers=h,
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text

        # Confirm both exist BEFORE delete
        r = requests.get(f"{API}/profiles/admin/{mid}", headers=h, timeout=15)
        assert r.status_code == 200, f"profile should exist pre-delete: {r.text}"
        r = requests.get(f"{API}/notifications/me/unread-count", headers=uh, timeout=15)
        assert r.status_code == 200
        pre_unread = r.json()["unread"]
        assert pre_unread >= 1

        # DELETE with granular scopes: only notifications, NOT profile
        body = {
            "confirmation": "DELETE USER",
            "wipe_profile": False,
            "wipe_notifications": True,
            "wipe_purchases": False,
            "wipe_certificates": False,
            "wipe_assessments": False,
            "wipe_bank_details": False,
            "wipe_commissions": False,
            "wipe_referral_tree": False,
        }
        r = requests.delete(f"{API}/admin/danger/users/{mid}", json=body, headers=h, timeout=15)
        assert r.status_code == 200, r.text
        wiped = r.json().get("wiped", {})

        # Notifications counted in wiped
        assert "notifications" in wiped, f"wiped missing 'notifications' key: {wiped}"
        assert wiped["notifications"] >= 1, f"expected notifications wipe count>=1, got {wiped}"

        # Profile NOT in wiped
        assert "profiles" not in wiped, f"profile should NOT have been wiped: {wiped}"

        # DB-level verification via admin endpoints:
        # Profile row still exists.
        r = requests.get(f"{API}/profiles/admin/{mid}", headers=h, timeout=15)
        assert r.status_code == 200, f"profile row wiped despite wipe_profile=False: {r.status_code} {r.text}"

        # Referral tree row still present
        r = requests.get(f"{API}/referral-tree/admin/{mid}", headers=h, timeout=15)
        assert r.status_code == 200, f"referral tree wiped despite wipe_referral_tree=False: {r.text}"

    def test_default_referral_tree_preserved(self):
        """Even with default checkboxes, referral_tree row must survive."""
        h = _admin_headers()
        m = _rand_mobile()
        reg = _register_user(m)
        mid = reg["user"]["membership_id"]

        # Default request payload from FE (defaultOptions())
        body = {
            "confirmation": "DELETE USER",
            "wipe_profile": True,
            "wipe_notifications": True,
            "wipe_purchases": False,
            "wipe_certificates": False,
            "wipe_assessments": False,
            "wipe_bank_details": False,
            "wipe_commissions": False,
            "wipe_referral_tree": False,
        }
        r = requests.delete(f"{API}/admin/danger/users/{mid}", json=body, headers=h, timeout=15)
        assert r.status_code == 200, r.text
        wiped = r.json().get("wiped", {})
        # Referral tree should NOT appear in wiped
        assert "referral_tree" not in wiped, f"referral_tree wiped by default: {wiped}"

        # Verify referral_tree admin lookup works
        r = requests.get(f"{API}/referral-tree/admin/{mid}", headers=h, timeout=15)
        assert r.status_code == 200, f"referral tree missing after default delete: {r.text}"

    def test_wipe_all_scopes(self):
        """Turning on every scope should return all keys in `wiped`."""
        h = _admin_headers()
        m = _rand_mobile()
        reg = _register_user(m)
        mid = reg["user"]["membership_id"]

        body = {
            "confirmation": "DELETE USER",
            "wipe_profile": True,
            "wipe_notifications": True,
            "wipe_purchases": True,
            "wipe_certificates": True,
            "wipe_assessments": True,
            "wipe_bank_details": True,
            "wipe_commissions": True,
            "wipe_referral_tree": True,
        }
        r = requests.delete(f"{API}/admin/danger/users/{mid}", json=body, headers=h, timeout=15)
        assert r.status_code == 200, r.text
        wiped = r.json().get("wiped", {})
        # All expected collection keys present
        for expected in ["profiles", "program_purchases", "notifications",
                         "certificates", "assessment_results", "bank_details",
                         "commissions", "referral_tree"]:
            assert expected in wiped, f"expected {expected} in wiped, got {wiped}"

        # Referral tree now really gone
        r = requests.get(f"{API}/referral-tree/admin/{mid}", headers=h, timeout=15)
        assert r.status_code in (404, 400), f"referral tree still present after wipe: {r.status_code}"

    def test_user_vanishes_from_admin_list(self):
        h = _admin_headers()
        m = _rand_mobile()
        reg = _register_user(m)
        mid = reg["user"]["membership_id"]

        r = requests.delete(
            f"{API}/admin/danger/users/{mid}",
            json={"confirmation": "DELETE USER"},
            headers=h,
            timeout=15,
        )
        assert r.status_code == 200, r.text

        r = requests.get(f"{API}/admin/users", headers=h, params={"page_size": 200}, timeout=15)
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert not any(u.get("membership_id") == mid for u in items), \
            f"deleted user {mid} still visible in admin list"


# =================================================================== FEATURE 3: notifications
class TestNotificationsRealtime:
    def test_unread_count_endpoint_shape(self):
        m = _rand_mobile()
        reg = _register_user(m)
        uh = _user_headers(reg)
        r = requests.get(f"{API}/notifications/me/unread-count", headers=uh, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict) and "unread" in data
        assert isinstance(data["unread"], int)

    def test_broadcast_reflects_on_unread_count(self):
        m = _rand_mobile()
        reg = _register_user(m)
        uh = _user_headers(reg)

        r = requests.get(f"{API}/notifications/me/unread-count", headers=uh, timeout=15)
        pre = r.json()["unread"]

        h = _admin_headers()
        r = requests.post(
            f"{API}/admin/notifications",
            json={
                "title": f"TEST_broadcast_{uuid.uuid4().hex[:6]}",
                "body": "iter20 broadcast poll test",
                "category": "announcement",
                "is_broadcast": True,
                "target_membership_ids": [],
            },
            headers=h,
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text

        r = requests.get(f"{API}/notifications/me/unread-count", headers=uh, timeout=15)
        assert r.status_code == 200
        post = r.json()["unread"]
        assert post == pre + 1, f"unread count did not bump: pre={pre} post={post}"

    def test_no_duplicate_rows_per_broadcast(self):
        """Regression from iter-18 fix: /me should return exactly 1 row per broadcast."""
        m = _rand_mobile()
        reg = _register_user(m)
        uh = _user_headers(reg)

        h = _admin_headers()
        title = f"TEST_uniq_{uuid.uuid4().hex[:6]}"
        r = requests.post(
            f"{API}/admin/notifications",
            json={
                "title": title,
                "body": "uniq check",
                "category": "system",
                "is_broadcast": True,
                "target_membership_ids": [],
            },
            headers=h,
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text

        r = requests.get(f"{API}/notifications/me", headers=uh, params={"page_size": 100}, timeout=15)
        assert r.status_code == 200
        items = r.json().get("items", [])
        matching = [n for n in items if n.get("title") == title]
        assert len(matching) == 1, f"expected exactly 1 row for broadcast, got {len(matching)}"
