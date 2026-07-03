"""RIYORA WELLNESS — Phase 8 Backend Regression Suite (Analytics + Reports).

Covers:
  * /api/analytics/dashboard (full aggregate)
  * /api/analytics/kpis (with compare=true)
  * /api/analytics/revenue (day/week/month granularity)
  * /api/analytics/leaderboard, /subscriptions, /programs, /states,
    /user-growth, /gst, /commissions
  * /api/admin/reports/{users, payments, referrals, subscriptions,
    activity, assessments, programs} — listing + filters
  * /api/admin/reports/*/export (csv | excel | pdf)
  * /api/analytics/me (user personal analytics)
  * /api/reports/{income,subscription,transaction,referral} multi-format
  * Admin + user auth guards
"""
from __future__ import annotations

import os
import random
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


def _register(referral_id: str = COMPANY_REF, name: str = "TEST_P8User"):
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
    return _register(name="TEST_P8_Fixture")


# ============ 1. ANALYTICS - ADMIN ========================================
class TestAnalyticsAdmin:
    def test_dashboard_shape(self, admin_h):
        r = requests.get(f"{API}/analytics/dashboard", headers=admin_h)
        assert r.status_code == 200, r.text
        d = r.json()
        required = {
            "range", "granularity", "kpis", "revenue_series", "user_growth",
            "programs", "states", "commissions", "subscriptions", "gst",
            "payouts", "leaderboard",
        }
        assert required.issubset(d.keys()), f"missing: {required - d.keys()}"
        assert "revenue" in d["kpis"]
        assert "users" in d["kpis"]
        assert "net_margin" in d["kpis"]
        assert isinstance(d["revenue_series"], list)
        assert "top_earners" in d["leaderboard"]
        assert "top_buyers" in d["leaderboard"]

    def test_kpis_with_compare(self, admin_h):
        r = requests.get(
            f"{API}/analytics/kpis?since=2026-06-01&until=2026-07-03&compare=true",
            headers=admin_h,
        )
        assert r.status_code == 200
        d = r.json()
        for k in ("revenue", "revenue_previous", "users", "commissions",
                  "payouts", "net_margin"):
            assert k in d, f"missing {k}"
        assert "revenue_change_pct" in d  # value may be None if prev revenue was 0

    def test_revenue_series_week(self, admin_h):
        r = requests.get(
            f"{API}/analytics/revenue?granularity=week&compare=true",
            headers=admin_h,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["granularity"] == "week"
        assert isinstance(d["series"], list)
        assert "previous_series" in d

    def test_revenue_series_month(self, admin_h):
        r = requests.get(
            f"{API}/analytics/revenue?granularity=month", headers=admin_h
        )
        assert r.status_code == 200
        assert r.json()["granularity"] == "month"

    def test_leaderboard(self, admin_h):
        r = requests.get(f"{API}/analytics/leaderboard?limit=5", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["top_earners"], list)
        assert isinstance(d["top_buyers"], list)
        assert len(d["top_earners"]) <= 5
        assert len(d["top_buyers"]) <= 5

    def test_subscriptions_health(self, admin_h):
        r = requests.get(f"{API}/analytics/subscriptions", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        for k in ("active", "expiring_7d", "expired"):
            assert k in d, f"missing {k}"
        assert "activity" in d
        for k in ("green", "yellow", "red"):
            assert k in d["activity"], f"missing activity.{k}"

    def test_programs_and_states(self, admin_h):
        r1 = requests.get(f"{API}/analytics/programs", headers=admin_h)
        assert r1.status_code == 200
        assert "items" in r1.json()

        r2 = requests.get(f"{API}/analytics/states", headers=admin_h)
        assert r2.status_code == 200
        assert "items" in r2.json()

    def test_user_growth(self, admin_h):
        r = requests.get(f"{API}/analytics/user-growth", headers=admin_h)
        assert r.status_code == 200
        assert "series" in r.json()

    def test_gst_and_commissions(self, admin_h):
        r1 = requests.get(f"{API}/analytics/gst", headers=admin_h)
        assert r1.status_code == 200

        r2 = requests.get(f"{API}/analytics/commissions", headers=admin_h)
        assert r2.status_code == 200
        d = r2.json()
        assert "summary" in d and "by_level" in d


# ============ 2. ADMIN REPORTS - LIST ======================================
class TestAdminReportsList:
    def test_users_report(self, admin_h):
        r = requests.get(
            f"{API}/admin/reports/users?page_size=5", headers=admin_h
        )
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("items", "total", "columns", "total_pages", "page", "page_size"):
            assert k in d
        assert isinstance(d["columns"], list)
        assert len(d["items"]) <= 5

    def test_payments_report_with_filter(self, admin_h):
        r = requests.get(
            f"{API}/admin/reports/payments?since=2020-01-01&until=2030-01-01"
            f"&status=active&page_size=5",
            headers=admin_h,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d
        # All items should have status=active if any
        for it in d["items"]:
            assert it.get("status") == "active"

    def test_referrals_report_level_filter(self, admin_h):
        r = requests.get(
            f"{API}/admin/reports/referrals?level=1&page_size=10", headers=admin_h
        )
        assert r.status_code == 200
        d = r.json()
        for it in d["items"]:
            assert it["level"] == 1

    def test_referrals_report_status_filter(self, admin_h):
        r = requests.get(
            f"{API}/admin/reports/referrals?status=pending&page_size=5",
            headers=admin_h,
        )
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert it["status"] == "pending"

    def test_subscriptions_activity_assessments_programs(self, admin_h):
        for rt in ("subscriptions", "activity", "assessments", "programs"):
            r = requests.get(
                f"{API}/admin/reports/{rt}?page_size=3", headers=admin_h
            )
            assert r.status_code == 200, f"{rt}: {r.text}"
            d = r.json()
            assert "items" in d
            assert "columns" in d
            assert d["report_type"] == rt

    def test_unknown_report_type_returns_400(self, admin_h):
        r = requests.get(f"{API}/admin/reports/unknown_xyz", headers=admin_h)
        assert r.status_code == 400


# ============ 3. ADMIN REPORTS - EXPORT ====================================
class TestAdminReportsExport:
    def test_payments_export_csv(self, admin_h):
        r = requests.get(
            f"{API}/admin/reports/payments/export?fmt=csv", headers=admin_h
        )
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("Content-Type", "")
        assert "attachment" in r.headers.get("Content-Disposition", "")
        assert len(r.content) > 100

    def test_payments_export_excel(self, admin_h):
        r = requests.get(
            f"{API}/admin/reports/payments/export?fmt=excel", headers=admin_h
        )
        assert r.status_code == 200
        ct = r.headers.get("Content-Type", "")
        assert "openxmlformats" in ct or "spreadsheetml" in ct
        assert len(r.content) > 500
        # xlsx is a zip archive
        assert r.content[:2] == b"PK"

    def test_payments_export_pdf(self, admin_h):
        r = requests.get(
            f"{API}/admin/reports/payments/export?fmt=pdf", headers=admin_h
        )
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("Content-Type", "")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 500

    def test_users_export_csv(self, admin_h):
        r = requests.get(
            f"{API}/admin/reports/users/export?fmt=csv", headers=admin_h
        )
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")
        assert len(r.content) > 100

    def test_referrals_export_excel_with_level_filter(self, admin_h):
        r = requests.get(
            f"{API}/admin/reports/referrals/export?fmt=excel&level=2",
            headers=admin_h,
        )
        assert r.status_code == 200, r.text
        assert r.content[:2] == b"PK"
        assert len(r.content) > 500


# ============ 4. USER ANALYTICS + REPORTS ==================================
class TestUserAnalyticsAndReports:
    def test_analytics_me_shape(self, user_h):
        r = requests.get(f"{API}/analytics/me", headers=user_h["headers"])
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("earnings", "earnings_series", "downline_series",
                  "downline_counts", "activity_meter", "spent"):
            assert k in d, f"missing {k}"
        assert set(d["downline_counts"].keys()) == {"L1", "L2", "L3"}

    def test_income_report_pdf_legacy(self, user_h):
        r = requests.get(
            f"{API}/reports/income?fmt=pdf", headers=user_h["headers"]
        )
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("Content-Type", "")
        assert r.content[:4] == b"%PDF"

    def test_income_report_csv(self, user_h):
        r = requests.get(
            f"{API}/reports/income?fmt=csv", headers=user_h["headers"]
        )
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")

    def test_income_report_excel(self, user_h):
        r = requests.get(
            f"{API}/reports/income?fmt=excel", headers=user_h["headers"]
        )
        assert r.status_code == 200
        assert r.content[:2] == b"PK"

    def test_subscription_report_csv(self, user_h):
        r = requests.get(
            f"{API}/reports/subscription?fmt=csv", headers=user_h["headers"]
        )
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")

    def test_transaction_report_excel(self, user_h):
        r = requests.get(
            f"{API}/reports/transaction?fmt=excel", headers=user_h["headers"]
        )
        assert r.status_code == 200
        assert r.content[:2] == b"PK"

    def test_referral_report_pdf(self, user_h):
        r = requests.get(
            f"{API}/reports/referral?fmt=pdf", headers=user_h["headers"]
        )
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("Content-Type", "")


# ============ 5. AUTH GUARDS =============================================
class TestAuthGuards:
    def test_analytics_dashboard_requires_admin(self):
        r = requests.get(f"{API}/analytics/dashboard")
        assert r.status_code in (401, 403)

    def test_admin_reports_payments_requires_admin(self):
        r = requests.get(f"{API}/admin/reports/payments")
        assert r.status_code in (401, 403)

    def test_analytics_me_requires_user(self):
        r = requests.get(f"{API}/analytics/me")
        assert r.status_code in (401, 403)

    def test_admin_endpoints_reject_user_token(self, user_h):
        for path in (
            "/analytics/dashboard",
            "/analytics/kpis",
            "/analytics/revenue",
            "/admin/reports/payments",
            "/admin/reports/users",
        ):
            r = requests.get(f"{API}{path}", headers=user_h["headers"])
            assert r.status_code in (401, 403), f"{path} → {r.status_code}"
