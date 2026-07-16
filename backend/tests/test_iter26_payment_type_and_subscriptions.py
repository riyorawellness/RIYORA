"""Iter26 — Payment Type (Free / One-Time / Subscription) + Referral Audit.

Covers:
- Program admin CRUD with payment_type=free | one_time | subscription
- Free-program enrolment endpoints (/programs/{id}/enrol-free, /programs/me/enrolments)
- Subscription init / verify / cancel flow (mock- or live-aware)
- program_status includes enrolment + active_subscription + has_access
- Referral audit JSON + PDF endpoints (/admin/qa/referral-audit[.pdf])
- BRV still 47/47 PASS

NOTE: Razorpay is LIVE in this sandbox (env RAZORPAY_MOCK_MODE=false,
      keys set). The subscription flow tests assert either mock OR live
      behaviour: if `is_mock=true` from init, we verify the mock path;
      otherwise we exercise the live path and cancel the sub afterwards
      so we don't pollute the Razorpay account.
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://rw-subscription-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PWD = "Admin@12345"

# Dummy tester (email+password fallback)
TESTER_EMAIL = "qa-tester@example.com"
TESTER_PWD = "tester123"


# ---------------------------------------------------------------- fixtures --

@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PWD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tester_token(admin_headers) -> str:
    # Try email+password login first (this is a legacy fallback endpoint accepting either mobile or email).
    r = requests.post(f"{API}/auth/login", json={"email": TESTER_EMAIL, "password": TESTER_PWD}, timeout=15)
    if r.status_code == 200:
        return r.json()["tokens"]["access_token"]
    # Fallback — create dummy user then login.
    create = requests.post(
        f"{API}/admin/users/dummy",
        headers=admin_headers,
        json={"full_name": "QA Tester", "email": TESTER_EMAIL, "password": TESTER_PWD},
        timeout=15,
    )
    # 409 = already exists; anything else = actual error
    if create.status_code not in (200, 201, 409):
        pytest.skip(f"Cannot create dummy tester: {create.status_code} {create.text}")
    r2 = requests.post(f"{API}/auth/login", json={"email": TESTER_EMAIL, "password": TESTER_PWD}, timeout=15)
    if r2.status_code != 200:
        pytest.skip(f"Dummy tester login failed: {r2.status_code} {r2.text}")
    return r2.json()["tokens"]["access_token"]


@pytest.fixture(scope="module")
def tester_headers(tester_token) -> dict:
    return {"Authorization": f"Bearer {tester_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def category_id(admin_headers) -> str:
    slug = f"testcat-{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{API}/categories/admin", headers=admin_headers,
        json={"name": "TEST Category", "slug": slug, "order_index": 999},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


_created_program_ids: list[str] = []
_created_subscription_ids: list[str] = []


def _create_program(admin_headers: dict, category_id: str, **overrides) -> dict:
    slug = f"testprog-{uuid.uuid4().hex[:6]}"
    body = {
        "name": overrides.get("name", "TEST Program"),
        "slug": slug,
        "price": overrides.get("price", 499),
        "validity_days": overrides.get("validity_days", 30),
        "category_id": category_id,
        "gst_percent": 0,
    }
    body.update({k: v for k, v in overrides.items() if k not in body})
    r = requests.post(f"{API}/programs/admin", headers=admin_headers, json=body, timeout=15)
    return r


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_headers):
    yield
    # Delete created programs
    for pid in _created_program_ids:
        try:
            requests.delete(f"{API}/programs/admin/{pid}", headers=admin_headers, timeout=10)
        except Exception:
            pass


# ================================================================ TESTS ==

# ------------ Program admin CRUD ------------

class TestAdminProgramPaymentType:

    def test_free_program_forces_price_zero_and_not_subscription(self, admin_headers, category_id):
        r = _create_program(admin_headers, category_id, payment_type="free", price=999)
        assert r.status_code == 201, r.text
        prog = r.json()
        _created_program_ids.append(prog["id"])
        assert prog["payment_type"] == "free"
        assert prog["price"] == 0
        assert prog["is_subscription"] is False

    def test_one_time_program_keeps_price(self, admin_headers, category_id):
        r = _create_program(admin_headers, category_id, payment_type="one_time", price=499)
        assert r.status_code == 201, r.text
        prog = r.json()
        _created_program_ids.append(prog["id"])
        assert prog["payment_type"] == "one_time"
        assert prog["price"] == 499
        assert prog["is_subscription"] is False

    def test_subscription_program_requires_frequency(self, admin_headers, category_id):
        # Missing frequency → 400
        r = _create_program(admin_headers, category_id, payment_type="subscription", price=499)
        assert r.status_code == 400, r.text
        assert "subscription_frequency" in r.json().get("detail", "").lower()

    def test_subscription_program_with_frequency_succeeds(self, admin_headers, category_id):
        r = _create_program(
            admin_headers, category_id,
            payment_type="subscription", price=499, subscription_frequency="monthly",
        )
        assert r.status_code == 201, r.text
        prog = r.json()
        _created_program_ids.append(prog["id"])
        assert prog["payment_type"] == "subscription"
        assert prog["is_subscription"] is True
        assert prog["subscription_frequency"] == "monthly"

    def test_update_one_time_to_free_sets_price_zero(self, admin_headers, category_id):
        # Create a one_time program first
        r = _create_program(admin_headers, category_id, payment_type="one_time", price=499)
        assert r.status_code == 201
        pid = r.json()["id"]
        _created_program_ids.append(pid)
        # Switch to free
        upd = requests.put(
            f"{API}/programs/admin/{pid}", headers=admin_headers,
            json={"payment_type": "free"}, timeout=15,
        )
        assert upd.status_code == 200, upd.text
        assert upd.json()["price"] == 0
        assert upd.json()["is_subscription"] is False

    def test_update_one_time_to_subscription_needs_frequency(self, admin_headers, category_id):
        r = _create_program(admin_headers, category_id, payment_type="one_time", price=499)
        assert r.status_code == 201
        pid = r.json()["id"]
        _created_program_ids.append(pid)
        upd = requests.put(
            f"{API}/programs/admin/{pid}", headers=admin_headers,
            json={"payment_type": "subscription"}, timeout=15,
        )
        assert upd.status_code == 400
        assert "subscription_frequency" in upd.json().get("detail", "").lower()


# ------------ Free program enrolment ------------

class TestFreeEnrolment:

    @pytest.fixture(scope="class")
    def free_program_id(self, admin_headers, category_id):
        r = _create_program(admin_headers, category_id, payment_type="free", price=0)
        assert r.status_code == 201
        pid = r.json()["id"]
        _created_program_ids.append(pid)
        return pid

    @pytest.fixture(scope="class")
    def one_time_program_id(self, admin_headers, category_id):
        r = _create_program(admin_headers, category_id, payment_type="one_time", price=499)
        assert r.status_code == 201
        pid = r.json()["id"]
        _created_program_ids.append(pid)
        return pid

    def test_enrol_free_success(self, tester_headers, free_program_id):
        r = requests.post(f"{API}/programs/{free_program_id}/enrol-free", headers=tester_headers, timeout=15)
        assert r.status_code == 201, r.text
        row = r.json()
        assert row["program_id"] == free_program_id
        assert row["source"] == "free"
        assert row["status"] == "active"

    def test_enrol_free_second_call_returns_409(self, tester_headers, free_program_id):
        r = requests.post(f"{API}/programs/{free_program_id}/enrol-free", headers=tester_headers, timeout=15)
        assert r.status_code == 409

    def test_enrol_free_on_non_free_returns_400(self, tester_headers, one_time_program_id):
        r = requests.post(f"{API}/programs/{one_time_program_id}/enrol-free", headers=tester_headers, timeout=15)
        assert r.status_code == 400

    def test_my_enrolments_returns_row(self, tester_headers, free_program_id):
        r = requests.get(f"{API}/programs/me/enrolments", headers=tester_headers, timeout=15)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert isinstance(payload.get("items"), list)
        assert any(e["program_id"] == free_program_id for e in payload["items"])

    def test_program_status_free_has_access(self, tester_headers, free_program_id):
        r = requests.get(f"{API}/programs/{free_program_id}/status", headers=tester_headers, timeout=15)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["has_access"] is True
        assert payload["enrolment"] is not None
        assert payload["enrolment"]["program_id"] == free_program_id


# ------------ Subscription flow (mock or live) ------------

class TestSubscriptionFlow:

    @pytest.fixture(scope="class")
    def sub_program_id(self, admin_headers, category_id):
        r = _create_program(
            admin_headers, category_id,
            payment_type="subscription", price=499, subscription_frequency="monthly",
        )
        assert r.status_code == 201
        pid = r.json()["id"]
        _created_program_ids.append(pid)
        return pid

    def test_subscription_init(self, tester_headers, sub_program_id, admin_headers):
        r = requests.post(
            f"{API}/payments/subscription/init", headers=tester_headers,
            json={"program_id": sub_program_id}, timeout=30,
        )
        # If live-mode Razorpay call fails (e.g., account limits), skip.
        if r.status_code == 502:
            pytest.skip(f"Razorpay live call failed: {r.text}")
        assert r.status_code == 201, r.text
        payload = r.json()
        assert "subscription_id" in payload
        assert "plan_id" in payload
        assert payload["frequency"] == "monthly"
        assert payload["amount_paise"] == 49900  # 499 * 100 (0% GST)
        _created_subscription_ids.append(payload["subscription_id"])
        # Store on class for downstream tests
        TestSubscriptionFlow._sub_id = payload["subscription_id"]
        TestSubscriptionFlow._is_mock = bool(payload.get("is_mock", False))

    def test_subscription_init_dup_returns_409(self, tester_headers, sub_program_id):
        # Need an already-authenticated sub. First verify to move to authenticated status.
        if not getattr(TestSubscriptionFlow, "_sub_id", None):
            pytest.skip("No sub id from previous test")
        sid = TestSubscriptionFlow._sub_id
        v = requests.post(f"{API}/payments/subscription/{sid}/verify", headers=tester_headers, timeout=20)
        # In mock mode fetch_subscription returns status='active'; in live mode
        # will return current status. Either way, if the sub is 'created' or 'authenticated'
        # it counts as active and second init should 409.
        if v.status_code == 502:
            pytest.skip("verify failed (live Razorpay)")
        assert v.status_code == 200, v.text
        r = requests.post(
            f"{API}/payments/subscription/init", headers=tester_headers,
            json={"program_id": sub_program_id}, timeout=15,
        )
        assert r.status_code == 409, r.text

    def test_subscription_cancel(self, tester_headers):
        sid = getattr(TestSubscriptionFlow, "_sub_id", None)
        if not sid:
            pytest.skip("No sub id")
        r = requests.post(f"{API}/payments/subscription/{sid}/cancel", headers=tester_headers, timeout=20)
        if r.status_code == 502:
            pytest.skip("Live razorpay cancel failed")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"
        # Second cancel → 409
        r2 = requests.post(f"{API}/payments/subscription/{sid}/cancel", headers=tester_headers, timeout=20)
        assert r2.status_code == 409


# ------------ Referral audit + BRV ------------

class TestReferralAudit:

    def test_referral_audit_json_pass(self, admin_headers):
        r = requests.get(f"{API}/admin/qa/referral-audit", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["overall"] == "PASS"
        expected_checks = {
            "company_root", "sponsor_mapping", "tree_depth",
            "commission_idempotency", "commission_calculation", "wallet_totals",
        }
        assert set(payload["checks"].keys()) == expected_checks
        assert payload["checks_passed"] == 6
        assert payload["checks_total"] == 6

    def test_referral_audit_pdf(self, admin_headers):
        r = requests.get(f"{API}/admin/qa/referral-audit.pdf", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 1024, f"PDF too small: {len(r.content)} bytes"
        assert r.content[:4] == b"%PDF"

    def test_brv_still_all_pass(self, admin_headers):
        r = requests.get(f"{API}/admin/qa/brv", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        payload = r.json()
        assert payload["overall"] == "PASS"
        # Should be 47/47 per review request
        assert payload["passed"] == 47, f"BRV passed count changed: {payload['passed']}"
        assert payload["failed"] == 0
