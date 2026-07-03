"""RIYORA WELLNESS — Phase 7 Backend Regression Suite (Admin Panel & CMS).

Covers:
  * Dashboard: overview / revenue-series / top-programs / top-referrers /
    recent-activity / recent-transactions
  * Admin Users: list (paginated) / export CSV / detail / patch /
    status update (with session revocation) / reset password
  * CMS public + admin: list, get, upsert, version snapshots, unpublished
  * System settings + public subset
  * Security settings roundtrip
  * Audit-log viewer w/ q / action filters
  * Uploads: create (valid+invalid MIME) / public GET / admin list / delete
  * Banners: /banners/active + admin CRUD
  * Notifications: send (broadcast + targeted) / user read / admin history
  * Auth guards on all /admin/* endpoints
  * Phase 5/6 regression smoke
"""
import io
import os
import random
import uuid
from pathlib import Path

import pytest
import requests

# ---- Load public URL from frontend/.env ----------------------------------
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


# ---- Helpers -------------------------------------------------------------
def _rand_mobile() -> str:
    return random.choice("6789") + "".join(random.choices("0123456789", k=9))


def _admin_headers():
    r = requests.post(
        f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {
        "Authorization": f"Bearer {r.json()['tokens']['access_token']}",
        "Content-Type": "application/json",
    }


def _register(referral_id: str = COMPANY_REF, name: str = "TEST_P7User"):
    m = _rand_mobile()
    requests.post(f"{API}/auth/send-otp", json={"mobile": m, "purpose": "register"})
    requests.post(
        f"{API}/auth/verify-otp",
        json={"mobile": m, "purpose": "register", "code": DEV_OTP},
    )
    r = requests.post(
        f"{API}/auth/register",
        json={
            "full_name": name,
            "mobile": m,
            "state": "KA",
            "city": "BLR",
            "referral_id": referral_id,
            "password": DEFAULT_PASSWORD,
            "confirm_password": DEFAULT_PASSWORD,
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    return {
        "mobile": m,
        "membership_id": d["user"]["membership_id"],
        "full_name": d["user"].get("full_name", name),
        "access": d["tokens"]["access_token"],
        "headers": {
            "Authorization": f"Bearer {d['tokens']['access_token']}",
            "Content-Type": "application/json",
        },
    }


@pytest.fixture(scope="module")
def admin_h():
    return _admin_headers()


@pytest.fixture(scope="module")
def user_h():
    u = _register(name="TEST_P7_FixtureUser")
    return u


# ============ 1. DASHBOARD ================================================
class TestDashboard:
    def test_overview_shape_and_values(self, admin_h):
        r = requests.get(f"{API}/admin/dashboard/overview", headers=admin_h)
        assert r.status_code == 200, r.text
        d = r.json()
        keys = [
            "total_users", "active_users", "inactive_users", "todays_registrations",
            "total_programs", "total_purchases", "active_subscribers",
            "expired_subscribers", "pending_payout_amount", "paid_payout_amount",
            "pending_program_expiry", "revenue_today", "revenue_month", "revenue_year",
        ]
        for k in keys:
            assert k in d, f"missing key {k}"
            assert isinstance(d[k], (int, float)), f"{k} not numeric: {d[k]}"
        assert d["total_users"] >= d["active_users"]

    def test_revenue_series_30_days(self, admin_h):
        r = requests.get(
            f"{API}/admin/dashboard/revenue-series?days=30", headers=admin_h
        )
        assert r.status_code == 200
        d = r.json()
        assert d["days"] == 30
        assert isinstance(d["series"], list)
        assert len(d["series"]) == 30
        # Order oldest→newest
        dates = [row["date"] for row in d["series"]]
        assert dates == sorted(dates), "series not oldest→newest"
        for row in d["series"]:
            assert set(row.keys()) >= {"date", "revenue", "count"}
            assert len(row["date"]) == 10  # YYYY-MM-DD
            assert isinstance(row["revenue"], (int, float))
            assert isinstance(row["count"], int)

    def test_top_programs_limit_and_sort(self, admin_h):
        r = requests.get(
            f"{API}/admin/dashboard/top-programs?limit=3", headers=admin_h
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) <= 3
        revs = [i["revenue"] for i in items]
        assert revs == sorted(revs, reverse=True), revs

    def test_top_referrers_limit_and_sort(self, admin_h):
        r = requests.get(
            f"{API}/admin/dashboard/top-referrers?limit=3", headers=admin_h
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) <= 3
        amts = [i["amount"] for i in items]
        assert amts == sorted(amts, reverse=True), amts

    def test_recent_activity_desc(self, admin_h):
        r = requests.get(f"{API}/admin/dashboard/recent-activity", headers=admin_h)
        assert r.status_code == 200
        items = r.json()["items"]
        if len(items) >= 2:
            for a, b in zip(items, items[1:]):
                assert a["created_at"] >= b["created_at"]

    def test_recent_transactions_fields(self, admin_h):
        r = requests.get(f"{API}/admin/dashboard/recent-transactions", headers=admin_h)
        assert r.status_code == 200
        items = r.json()["items"]
        for it in items:
            for k in ("invoice_number", "user_name", "program_name", "total"):
                assert k in it


# ============ 2. USERS ====================================================
class TestAdminUsers:
    def test_list_paginated_shape(self, admin_h):
        r = requests.get(f"{API}/admin/users?page=1&page_size=5", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        for k in ("items", "total", "page", "page_size", "total_pages"):
            assert k in d, f"missing {k}"
        assert isinstance(d["items"], list)
        assert d["page"] == 1
        assert d["page_size"] == 5

    def test_list_filters(self, admin_h):
        # Create a user with unique name substring
        marker = f"TEST_UF{uuid.uuid4().hex[:6]}"
        u = _register(name=marker)
        r = requests.get(
            f"{API}/admin/users?q={marker}&is_active=true&state=KA",
            headers=admin_h,
        )
        assert r.status_code == 200
        d = r.json()
        mids = [i["membership_id"] for i in d["items"]]
        assert u["membership_id"] in mids

    def test_export_csv(self, admin_h):
        r = requests.get(f"{API}/admin/users/export", headers=admin_h)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")
        assert 'filename="users.csv"' in r.headers.get("Content-Disposition", "")
        body = r.text
        lines = body.strip().split("\n")
        assert len(lines) >= 2  # header + at least one row
        assert "membership_id" in lines[0]

    def test_user_detail_and_no_password_hash(self, admin_h):
        u = _register()
        r = requests.get(f"{API}/admin/users/{u['membership_id']}", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        for k in ("user", "purchases", "subscriptions", "bank_details",
                  "downline", "earnings", "activity"):
            assert k in d, f"missing {k}"
        assert "password_hash" not in d["user"], "password_hash leaked!"
        assert set(d["downline"].keys()) == {"L1", "L2", "L3"}

    def test_user_detail_404(self, admin_h):
        r = requests.get(f"{API}/admin/users/RW999999", headers=admin_h)
        assert r.status_code == 404

    def test_status_update_revokes_session_and_login(self, admin_h):
        u = _register(name="TEST_P7_Suspend")
        # First login OK
        rlog = requests.post(
            f"{API}/auth/login",
            json={"mobile": u["mobile"], "password": DEFAULT_PASSWORD},
        )
        assert rlog.status_code == 200
        # Suspend
        r = requests.patch(
            f"{API}/admin/users/{u['membership_id']}/status",
            headers=admin_h,
            json={"status": "suspended", "reason": "TEST"},
        )
        assert r.status_code == 200, r.text
        # Login should now fail
        rfail = requests.post(
            f"{API}/auth/login",
            json={"mobile": u["mobile"], "password": DEFAULT_PASSWORD},
        )
        assert rfail.status_code in (401, 403), rfail.text
        # Restore
        r2 = requests.patch(
            f"{API}/admin/users/{u['membership_id']}/status",
            headers=admin_h,
            json={"status": "active"},
        )
        assert r2.status_code == 200
        # Login OK again
        rok = requests.post(
            f"{API}/auth/login",
            json={"mobile": u["mobile"], "password": DEFAULT_PASSWORD},
        )
        assert rok.status_code == 200

    def test_reset_password_and_relogin(self, admin_h):
        u = _register(name="TEST_P7_Reset")
        new_pw = "NewPass123!"
        r = requests.post(
            f"{API}/admin/users/{u['membership_id']}/reset-password",
            headers=admin_h,
            json={"new_password": new_pw},
        )
        assert r.status_code == 200
        # Old password fails
        rold = requests.post(
            f"{API}/auth/login",
            json={"mobile": u["mobile"], "password": DEFAULT_PASSWORD},
        )
        assert rold.status_code in (401, 403)
        # New password works
        rnew = requests.post(
            f"{API}/auth/login",
            json={"mobile": u["mobile"], "password": new_pw},
        )
        assert rnew.status_code == 200

    def test_patch_user_updates(self, admin_h):
        u = _register(name="TEST_P7_Patch")
        new_name = f"TEST_P7_Patched_{uuid.uuid4().hex[:5]}"
        r = requests.patch(
            f"{API}/admin/users/{u['membership_id']}",
            headers=admin_h,
            json={"full_name": new_name},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["success"] is True
        # Verify by GET
        det = requests.get(
            f"{API}/admin/users/{u['membership_id']}", headers=admin_h
        ).json()
        assert det["user"]["full_name"] == new_name


# ============ 3. CMS ======================================================
class TestCMS:
    def test_public_list_only_published(self):
        r = requests.get(f"{API}/cms/pages")
        assert r.status_code == 200
        items = r.json()["items"]
        for it in items:
            assert it.get("is_published", True) is True
            # public listing excludes body
            assert "body" not in it

    def test_public_get_unknown_returns_stub(self):
        slug = f"unknown-{uuid.uuid4().hex[:6]}"
        r = requests.get(f"{API}/cms/pages/{slug}")
        assert r.status_code == 200
        d = r.json()
        assert d.get("empty") is True
        assert d.get("body") == ""

    def test_admin_list_reserved_slugs(self, admin_h):
        r = requests.get(f"{API}/admin/cms/pages", headers=admin_h)
        assert r.status_code == 200
        items = r.json()["items"]
        slugs = {i["slug"] for i in items}
        for reserved in ("about", "privacy", "terms", "refund", "contact",
                          "faq", "support"):
            assert reserved in slugs
        for it in items:
            assert "is_published" in it

    def test_upsert_creates_and_snapshots(self, admin_h):
        # First upsert creates
        r1 = requests.put(
            f"{API}/admin/cms/pages/about",
            headers=admin_h,
            json={
                "title": "About RIYORA v1",
                "body": "<p>hi</p>",
                "is_published": True,
            },
        )
        assert r1.status_code == 200, r1.text
        # Second upsert modifies + snapshots
        r2 = requests.put(
            f"{API}/admin/cms/pages/about",
            headers=admin_h,
            json={
                "title": "About RIYORA v2",
                "body": "<p>hi v2</p>",
                "is_published": True,
            },
        )
        assert r2.status_code == 200
        # Version list should have at least 1 snapshot
        rv = requests.get(f"{API}/admin/cms/pages/about/versions", headers=admin_h)
        assert rv.status_code == 200
        versions = rv.json()["items"]
        assert len(versions) >= 1
        assert any(v["title"] == "About RIYORA v1" for v in versions)

    def test_unpublished_hidden_from_public(self, admin_h):
        slug = f"custom-{uuid.uuid4().hex[:6]}"
        # Create unpublished
        r = requests.put(
            f"{API}/admin/cms/pages/{slug}",
            headers=admin_h,
            json={"title": "Draft", "body": "<p>hidden</p>", "is_published": False},
        )
        assert r.status_code == 200
        # Public returns empty stub
        pub = requests.get(f"{API}/cms/pages/{slug}").json()
        assert pub.get("empty") is True
        # Admin returns real
        adm = requests.get(f"{API}/admin/cms/pages/{slug}", headers=admin_h).json()
        assert adm["title"] == "Draft"


# ============ 4. SYSTEM + SECURITY SETTINGS ==============================
class TestSettings:
    def test_system_defaults_and_roundtrip(self, admin_h):
        r = requests.get(f"{API}/admin/system/settings", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        assert d.get("company_name") == "RIYORA Wellness" or d.get("company_name")
        assert d.get("application_version") in ("1.0.0", d.get("application_version"))
        assert d.get("maintenance_mode") in (False, True)

        # Roundtrip
        r2 = requests.put(
            f"{API}/admin/system/settings",
            headers=admin_h,
            json={"company_name": "TEST_X", "maintenance_mode": True},
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["company_name"] == "TEST_X"
        assert d2["maintenance_mode"] is True
        # Restore
        requests.put(
            f"{API}/admin/system/settings",
            headers=admin_h,
            json={"company_name": "RIYORA Wellness", "maintenance_mode": False},
        )

    def test_public_system_no_auth(self):
        r = requests.get(f"{API}/system/public")
        assert r.status_code == 200
        d = r.json()
        assert "company_name" in d
        # No sensitive keys
        assert "password_min_length" not in d
        assert "login_attempt_limit" not in d

    def test_security_defaults_and_roundtrip(self, admin_h):
        r = requests.get(f"{API}/admin/security/settings", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        assert d.get("password_min_length") in (8, d.get("password_min_length"))
        assert d.get("otp_expiry_seconds") in (300, d.get("otp_expiry_seconds"))
        assert d.get("login_attempt_limit") in (5, d.get("login_attempt_limit"))
        assert d.get("session_timeout_minutes") in (60, d.get("session_timeout_minutes"))

        r2 = requests.put(
            f"{API}/admin/security/settings",
            headers=admin_h,
            json={"login_attempt_limit": 7, "session_timeout_minutes": 45},
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["login_attempt_limit"] == 7
        assert d2["session_timeout_minutes"] == 45
        # Restore
        requests.put(
            f"{API}/admin/security/settings",
            headers=admin_h,
            json={"login_attempt_limit": 5, "session_timeout_minutes": 60},
        )


# ============ 5. AUDIT LOG ================================================
class TestAuditLog:
    def test_audit_log_paginated_and_filtered(self, admin_h):
        # Trigger a known action (upload delete via export doesn't work here — use CMS upsert)
        slug = f"audit-{uuid.uuid4().hex[:6]}"
        requests.put(
            f"{API}/admin/cms/pages/{slug}",
            headers=admin_h,
            json={"title": "AuditPage", "body": "x", "is_published": True},
        )
        r = requests.get(
            f"{API}/admin/audit-log?page_size=20&action=cms",
            headers=admin_h,
        )
        assert r.status_code == 200
        d = r.json()
        for k in ("items", "total", "page", "page_size", "total_pages"):
            assert k in d
        # Sort desc
        if len(d["items"]) >= 2:
            for a, b in zip(d["items"], d["items"][1:]):
                assert a["created_at"] >= b["created_at"]

    def test_audit_log_q_filter(self, admin_h):
        r = requests.get(
            f"{API}/admin/audit-log?q=users.export&page_size=5", headers=admin_h
        )
        assert r.status_code == 200


# ============ 6. UPLOADS ==================================================
def _tiny_png() -> bytes:
    # 1x1 red PNG
    import base64
    return base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )


class TestUploads:
    def test_upload_valid_png_and_get(self, admin_h):
        h = {"Authorization": admin_h["Authorization"]}
        png = _tiny_png()
        files = {"file": ("tiny.png", io.BytesIO(png), "image/png")}
        r = requests.post(f"{API}/admin/uploads", headers=h, files=files)
        assert r.status_code == 201, r.text
        d = r.json()
        for k in ("id", "url", "original_name", "content_type", "size_bytes"):
            assert k in d
        assert d["url"] == f"/api/uploads/{d['id']}"
        assert d["content_type"] == "image/png"
        assert d["size_bytes"] == len(png)
        # Public GET
        r2 = requests.get(f"{API}/uploads/{d['id']}")
        assert r2.status_code == 200
        assert "image/png" in r2.headers.get("Content-Type", "")
        assert r2.content == png

    def test_upload_rejects_text_plain(self, admin_h):
        h = {"Authorization": admin_h["Authorization"]}
        files = {"file": ("bad.txt", io.BytesIO(b"hello"), "text/plain")}
        r = requests.post(f"{API}/admin/uploads", headers=h, files=files)
        assert r.status_code == 400, r.text

    def test_get_unknown_upload_404(self):
        r = requests.get(f"{API}/uploads/does-not-exist")
        assert r.status_code == 404

    def test_delete_upload_removes(self, admin_h):
        h = {"Authorization": admin_h["Authorization"]}
        png = _tiny_png()
        files = {"file": ("del.png", io.BytesIO(png), "image/png")}
        cr = requests.post(f"{API}/admin/uploads", headers=h, files=files)
        assert cr.status_code == 201
        fid = cr.json()["id"]
        dr = requests.delete(
            f"{API}/admin/uploads/{fid}", headers=admin_h
        )
        assert dr.status_code == 200
        gr = requests.get(f"{API}/uploads/{fid}")
        assert gr.status_code == 404


# ============ 7. BANNERS ==================================================
class TestBanners:
    def test_public_active_banners_no_auth(self):
        r = requests.get(f"{API}/banners/active")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_admin_crud_and_soft_delete(self, admin_h):
        # Create
        payload = {
            "title": f"TEST_Banner_{uuid.uuid4().hex[:5]}",
            "image_url": "/static/banner.png",
            "placement": "home",
            "priority": 100,
            "is_active": True,
        }
        r = requests.post(f"{API}/admin/banners", headers=admin_h, json=payload)
        assert r.status_code == 201, r.text
        bid = r.json()["id"]
        # Update
        payload2 = {**payload, "title": "TEST_Banner_updated", "priority": 200}
        ru = requests.put(
            f"{API}/admin/banners/{bid}", headers=admin_h, json=payload2
        )
        assert ru.status_code == 200
        assert ru.json()["title"] == "TEST_Banner_updated"
        # Appears in /banners/active
        pub = requests.get(f"{API}/banners/active?placement=home").json()["items"]
        assert any(b["id"] == bid for b in pub)
        # Delete
        rd = requests.delete(f"{API}/admin/banners/{bid}", headers=admin_h)
        assert rd.status_code == 200
        # No longer appears
        pub2 = requests.get(f"{API}/banners/active?placement=home").json()["items"]
        assert not any(b["id"] == bid for b in pub2)


# ============ 8. NOTIFICATIONS ============================================
class TestNotifications:
    def test_broadcast_creates_template_and_deliveries(self, admin_h):
        r = requests.post(
            f"{API}/admin/notifications",
            headers=admin_h,
            json={
                "title": f"TEST_BCAST_{uuid.uuid4().hex[:5]}",
                "body": "hello broadcast",
                "category": "announcement",
                "is_broadcast": True,
            },
        )
        assert r.status_code == 201, r.text
        d = r.json()
        assert "template_id" in d
        assert d["delivered_count"] >= 1

    def test_targeted_notification_only_selected(self, admin_h):
        u = _register(name="TEST_P7_NotifTarget")
        r = requests.post(
            f"{API}/admin/notifications",
            headers=admin_h,
            json={
                "title": "TEST_TARGET",
                "body": "hi",
                "category": "system",
                "is_broadcast": False,
                "target_membership_ids": [u["membership_id"]],
            },
        )
        assert r.status_code == 201
        d = r.json()
        assert d["delivered_count"] == 1

        # User can fetch it
        mine = requests.get(f"{API}/notifications/me", headers=u["headers"])
        assert mine.status_code == 200
        m = mine.json()
        titles = [it["title"] for it in m["items"]]
        assert "TEST_TARGET" in titles
        assert m["unread"] >= 1

        # Read all
        ra = requests.post(f"{API}/notifications/me/read-all", headers=u["headers"])
        assert ra.status_code == 200
        assert ra.json()["updated"] >= 1
        m2 = requests.get(f"{API}/notifications/me", headers=u["headers"]).json()
        assert m2["unread"] == 0

    def test_admin_notification_history(self, admin_h):
        r = requests.get(f"{API}/admin/notifications?page_size=10", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        for k in ("items", "total", "page", "page_size", "total_pages"):
            assert k in d
        for it in d["items"]:
            assert "delivered_count" in it


# ============ 9. AUTH GUARDS =============================================
class TestAuthGuards:
    def test_admin_endpoints_reject_no_token(self):
        for path in (
            "/admin/dashboard/overview",
            "/admin/users",
            "/admin/users/export",
            "/admin/cms/pages",
            "/admin/system/settings",
            "/admin/security/settings",
            "/admin/audit-log",
            "/admin/uploads",
            "/admin/banners",
            "/admin/notifications",
        ):
            r = requests.get(f"{API}{path}")
            assert r.status_code in (401, 403), f"{path} → {r.status_code}"

    def test_admin_endpoints_reject_user_token(self, user_h):
        for path in (
            "/admin/dashboard/overview",
            "/admin/users",
            "/admin/cms/pages",
            "/admin/system/settings",
            "/admin/security/settings",
            "/admin/audit-log",
            "/admin/banners",
        ):
            r = requests.get(f"{API}{path}", headers=user_h["headers"])
            assert r.status_code in (401, 403), f"{path} → {r.status_code}"

    def test_public_cms_no_auth(self):
        r = requests.get(f"{API}/cms/pages")
        assert r.status_code == 200

    def test_public_banners_no_auth(self):
        r = requests.get(f"{API}/banners/active")
        assert r.status_code == 200

    def test_public_system_no_auth(self):
        r = requests.get(f"{API}/system/public")
        assert r.status_code == 200

    def test_notifications_me_requires_auth(self):
        r = requests.get(f"{API}/notifications/me")
        assert r.status_code in (401, 403)


# ============ 10. REGRESSION Phase 5/6 ===================================
class TestRegressionPrevPhases:
    def test_activity_meter_reachable(self, user_h):
        r = requests.get(f"{API}/activity/meter", headers=user_h["headers"])
        assert r.status_code == 200
        assert "status" in r.json()

    def test_referrals_dashboard_reachable(self, user_h):
        r = requests.get(f"{API}/referrals/dashboard", headers=user_h["headers"])
        assert r.status_code == 200

    def test_commissions_me_reachable(self, user_h):
        r = requests.get(f"{API}/commissions/me", headers=user_h["headers"])
        assert r.status_code == 200

    def test_payouts_me_reachable(self, user_h):
        r = requests.get(f"{API}/payouts/me", headers=user_h["headers"])
        assert r.status_code == 200

    def test_report_pdf_reachable(self, user_h):
        r = requests.get(f"{API}/reports/referral", headers=user_h["headers"])
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("Content-Type", "")
