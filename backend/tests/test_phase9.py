"""Phase 9 — Security, Health, BRV, PWA/SEO backend tests.

Covers:
    * BRV JSON + PDF (admin only)
    * Brute-force lockout on /api/auth/login and /api/admin/login
    * Security headers on responses
    * X-Request-ID header
    * /api/health/live, /ready, /deep
    * Regression spot-checks (dashboard/overview, analytics/dashboard,
      admin/reports/payments, reports/income?fmt=pdf)
    * SEO: /robots.txt, /sitemap.xml, index.html og/twitter tags
"""
from __future__ import annotations

import os
import re

import pytest
import requests


def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # fallback: read from frontend .env
        env_path = "/app/frontend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    assert url, "REACT_APP_BACKEND_URL not set anywhere"
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"


# ---------- Fixtures --------------------------------------------------------


@pytest.fixture(scope="module")
def admin_token() -> str:
    # Ensure lockout table is clear before login (in case prior tests left state)
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json()["tokens"]["access_token"]
    assert tok and isinstance(tok, str)
    return tok


@pytest.fixture
def admin_client(admin_token) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    )
    return s


# ---------- Health endpoints -----------------------------------------------


class TestHealth:
    def test_live_no_auth(self):
        r = requests.get(f"{API}/health/live", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    def test_ready_no_auth(self):
        r = requests.get(f"{API}/health/ready", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["mongo"] == "ok"

    def test_deep_requires_auth(self):
        r = requests.get(f"{API}/health/deep", timeout=10)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_deep_with_admin(self, admin_client):
        r = admin_client.get(f"{API}/health/deep", timeout=15)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["status"] in ("ok", "degraded")
        assert "mongo_ping_ms" in b and isinstance(b["mongo_ping_ms"], int)
        assert "uptime_seconds" in b and isinstance(b["uptime_seconds"], int)
        assert "counts" in b and isinstance(b["counts"], dict)
        for c in ["users", "memberships", "programs", "program_purchases"]:
            assert c in b["counts"], f"missing count: {c}"
        assert "errors_24h" in b


# ---------- Security headers & X-Request-ID --------------------------------


class TestSecurityMiddleware:
    def test_security_headers_present(self):
        r = requests.get(f"{API}/health/live", timeout=10)
        assert r.status_code == 200
        h = {k.lower(): v for k, v in r.headers.items()}
        assert h.get("x-content-type-options") == "nosniff"
        assert h.get("x-frame-options") == "SAMEORIGIN"
        assert "referrer-policy" in h
        assert "strict-transport-security" in h
        assert "content-security-policy" in h

    def test_request_id_header(self):
        r = requests.get(f"{API}/health/live", timeout=10)
        rid = r.headers.get("X-Request-ID") or r.headers.get("x-request-id")
        assert rid, "X-Request-ID header missing"
        assert len(rid) >= 8


# ---------- BRV -------------------------------------------------------------


class TestBRV:
    def test_brv_requires_auth(self):
        r = requests.get(f"{API}/admin/qa/brv", timeout=15)
        assert r.status_code in (401, 403)

    def test_brv_json(self, admin_client):
        r = admin_client.get(f"{API}/admin/qa/brv", timeout=60)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["total"] == 36, f"expected 36 rules, got {b['total']}"
        assert b["passed"] == 36, f"expected 36 passed, got {b['passed']}. Failed: {[x for x in b['rules'] if x['status']!='Pass']}"
        assert b["failed"] == 0
        assert b["overall"] == "PASS"
        assert "by_category" in b and isinstance(b["by_category"], dict)
        assert "rules" in b and len(b["rules"]) == 36
        for r_ in b["rules"]:
            for k in ("id", "category", "name", "expected", "actual", "status", "remarks"):
                assert k in r_, f"rule missing field {k}: {r_}"

    def test_brv_pdf(self, admin_client):
        r = admin_client.get(f"{API}/admin/qa/brv/pdf", timeout=60)
        assert r.status_code == 200, r.text
        assert r.headers.get("Content-Type", "").startswith("application/pdf")
        assert len(r.content) > 5000, f"pdf too small: {len(r.content)}"
        cd = r.headers.get("Content-Disposition", "")
        assert "attachment" in cd.lower()


# ---------- Brute-force lockout --------------------------------------------


def _cleanup_lockout(mobile: str, role: str):
    """Directly clear login_attempts via mongo to avoid stale state."""
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        client = MongoClient(mongo_url)
        client[db_name].login_attempts.delete_one({"mobile": mobile, "role": role})
        client.close()
    except Exception as e:
        print(f"[cleanup warn] {e}")


class TestBruteForceLockout:
    def test_user_login_lockout(self):
        mobile = "8888800001"
        # 5 wrong attempts should be 401; 6th should be 429
        for i in range(5):
            r = requests.post(
                f"{API}/auth/login",
                json={"mobile": mobile, "password": "WrongPass1!"},
                timeout=15,
            )
            assert r.status_code in (401, 429), f"attempt {i+1}: unexpected {r.status_code} {r.text}"
        r6 = requests.post(
            f"{API}/auth/login",
            json={"mobile": mobile, "password": "WrongPass1!"},
            timeout=15,
        )
        assert r6.status_code == 429, f"6th attempt should be 429, got {r6.status_code} {r6.text}"
        detail = r6.json().get("detail", "")
        assert "Too many failed login" in detail
        assert "minute" in detail
        _cleanup_lockout(mobile, "user")

    def test_admin_login_lockout(self):
        mobile = ADMIN_MOBILE
        # Ensure clean state
        _cleanup_lockout(mobile, "admin")
        for i in range(5):
            r = requests.post(
                f"{API}/admin/login",
                json={"mobile": mobile, "password": "WrongAdminPw!"},
                timeout=15,
            )
            assert r.status_code in (401, 429), f"attempt {i+1}: unexpected {r.status_code}"
        r6 = requests.post(
            f"{API}/admin/login",
            json={"mobile": mobile, "password": "WrongAdminPw!"},
            timeout=15,
        )
        assert r6.status_code == 429, f"6th admin attempt should be 429, got {r6.status_code}"
        detail = r6.json().get("detail", "")
        assert "Too many failed login" in detail
        # CRITICAL: cleanup so subsequent runs can login as admin!
        _cleanup_lockout(mobile, "admin")

    def test_successful_login_clears_attempts(self):
        # Register a real user to test success clearing
        # Simpler: use the admin login flow, which we know works.
        mobile = ADMIN_MOBILE
        _cleanup_lockout(mobile, "admin")
        # 2 failed attempts
        for _ in range(2):
            requests.post(
                f"{API}/admin/login",
                json={"mobile": mobile, "password": "WrongPass1!"},
                timeout=15,
            )
        # successful login clears
        r = requests.post(
            f"{API}/admin/login",
            json={"mobile": mobile, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200
        # Verify record was cleared by making 5 wrong attempts and expecting 429 only on 6th (fresh counter)
        for i in range(5):
            rr = requests.post(
                f"{API}/admin/login",
                json={"mobile": mobile, "password": "WrongPass1!"},
                timeout=15,
            )
            assert rr.status_code == 401, f"After clear, attempt {i+1} should be 401 not {rr.status_code}"
        _cleanup_lockout(mobile, "admin")


# ---------- Regression spot-checks -----------------------------------------


class TestRegressions:
    def test_admin_dashboard_overview(self, admin_client):
        r = admin_client.get(f"{API}/admin/dashboard/overview", timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), dict)

    def test_analytics_dashboard(self, admin_client):
        r = admin_client.get(f"{API}/analytics/dashboard", timeout=15)
        assert r.status_code == 200, r.text

    def test_admin_reports_payments(self, admin_client):
        r = admin_client.get(f"{API}/admin/reports/payments", timeout=15)
        assert r.status_code == 200, r.text
        b = r.json()
        assert "items" in b or "data" in b or "rows" in b or isinstance(b, list)

    def test_income_report_pdf(self):
        """Income report PDF requires user token, not admin — register a test user."""
        import random
        mobile = "9" + str(random.randint(100000000, 999999999))
        # send OTP
        r = requests.post(
            f"{API}/auth/send-otp",
            json={"mobile": mobile, "purpose": "register"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        # verify OTP
        r = requests.post(
            f"{API}/auth/verify-otp",
            json={"mobile": mobile, "purpose": "register", "code": "123456"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        # register
        r = requests.post(
            f"{API}/auth/register",
            json={
                "full_name": "TEST_P9_ReportsUser",
                "mobile": mobile,
                "state": "Karnataka",
                "city": "Bengaluru",
                "password": "Passw0rd!",
                "referral_id": "RW000000",
                "confirm_password": "Passw0rd!",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        access = r.json()["tokens"]["access_token"]
        # income PDF
        r = requests.get(
            f"{API}/reports/income?fmt=pdf",
            headers={"Authorization": f"Bearer {access}"},
            timeout=30,
        )
        assert r.status_code == 200, f"income pdf failed: {r.status_code} {r.text[:200]}"
        assert r.headers.get("Content-Type", "").startswith("application/pdf")
        assert len(r.content) > 1000


# ---------- SEO / PWA ------------------------------------------------------


class TestSEO:
    def test_robots_txt(self):
        r = requests.get(f"{BASE_URL}/robots.txt", timeout=10)
        assert r.status_code == 200, r.status_code
        assert "User-agent: *" in r.text

    def test_sitemap_xml(self):
        r = requests.get(f"{BASE_URL}/sitemap.xml", timeout=10)
        assert r.status_code == 200
        assert "<urlset" in r.text

    def test_og_meta_tags(self):
        r = requests.get(f"{BASE_URL}/", timeout=10)
        assert r.status_code == 200
        html = r.text
        assert re.search(r'property=["\']og:title["\']', html), "og:title missing"
        assert re.search(r'property=["\']og:description["\']', html), "og:description missing"
        assert re.search(r'name=["\']twitter:card["\']', html), "twitter:card missing"
