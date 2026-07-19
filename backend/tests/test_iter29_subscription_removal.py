"""iter29 — Verify Razorpay Subscription/AutoPay flow removal.

Requirements:
1. All 4 subscription endpoints must return 404.
2. Free enrolment must still work (regression).
3. One-time Razorpay flow must work end-to-end in mock mode (regression).
4. Webhook coverage returns exactly 3 required_events, all category=one_time.
5. Admin program create accepts free/one_time; rejects or silently coerces subscription.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

def _load_backend_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if url:
        return url.rstrip("/")
    # Fallback: read from /app/frontend/.env
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"
DUMMY_EMAIL = "qa-tester@example.com"
DUMMY_PASSWORD = "tester123"


# =========================================================================
# Fixtures
# =========================================================================
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": DUMMY_EMAIL, "password": DUMMY_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Dummy user login failed: {r.status_code} {r.text}")
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# =========================================================================
# 1) Subscription endpoints must be gone (404)
# =========================================================================
class TestSubscriptionEndpointsRemoved:
    def test_subscription_init_404(self, user_headers):
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers=user_headers,
            json={"program_id": "any"},
            timeout=10,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"

    def test_subscription_me_404(self, user_headers):
        r = requests.get(
            f"{API}/payments/subscription/me", headers=user_headers, timeout=10
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"

    def test_subscription_verify_404(self, user_headers):
        r = requests.post(
            f"{API}/payments/subscription/sub_abc/verify",
            headers=user_headers,
            json={},
            timeout=10,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"

    def test_subscription_cancel_404(self, user_headers):
        r = requests.post(
            f"{API}/payments/subscription/sub_abc/cancel",
            headers=user_headers,
            json={},
            timeout=10,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"


# =========================================================================
# 2) Webhook coverage — exactly 3 events, all category=one_time
# =========================================================================
class TestWebhookCoverage:
    def test_coverage_shape(self, admin_headers):
        r = requests.get(
            f"{API}/admin/qa/live-check/webhook-coverage",
            headers=admin_headers,
            timeout=10,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        required = data.get("required_events", [])
        assert set(required) == {
            "payment.captured",
            "order.paid",
            "payment.failed",
        }, f"Unexpected required_events: {required}"
        checklist = data.get("checklist", [])
        assert len(checklist) == 3, f"Expected 3 checklist items, got {len(checklist)}"
        for item in checklist:
            assert item.get("category") == "one_time", f"Non-one_time entry: {item}"

    def test_coverage_requires_admin(self):
        r = requests.get(f"{API}/admin/qa/live-check/webhook-coverage", timeout=10)
        assert r.status_code in (401, 403), f"Expected auth error, got {r.status_code}"


# =========================================================================
# 3) Free enrolment regression
# =========================================================================
class TestFreeEnrolmentRegression:
    program_id = None
    program_id_paid = None

    @pytest.fixture(scope="class", autouse=True)
    def _seed_program(self, admin_headers):
        # Create/ensure a category
        cat_body = {
            "name": "TEST_iter29_cat",
            "slug": f"test-iter29-cat-{uuid.uuid4().hex[:6]}",
            "order_index": 99,
        }
        cr = requests.post(
            f"{API}/categories/admin",
            headers=admin_headers,
            json=cat_body,
            timeout=10,
        )
        assert cr.status_code in (200, 201), cr.text
        cat_id = cr.json()["id"]

        # Create a FREE program
        free_body = {
            "name": "TEST_iter29_free_program",
            "slug": f"test-iter29-free-{uuid.uuid4().hex[:6]}",
            "price": 0,
            "validity_days": 30,
            "category_id": cat_id,
            "payment_type": "free",
        }
        pr = requests.post(
            f"{API}/programs/admin", headers=admin_headers, json=free_body, timeout=10
        )
        assert pr.status_code in (200, 201), pr.text
        TestFreeEnrolmentRegression.program_id = pr.json()["id"]

        # Also a one_time program for the paid regression test
        paid_body = {
            "name": "TEST_iter29_onetime_program",
            "slug": f"test-iter29-ot-{uuid.uuid4().hex[:6]}",
            "price": 499,
            "validity_days": 30,
            "category_id": cat_id,
            "payment_type": "one_time",
        }
        pr2 = requests.post(
            f"{API}/programs/admin", headers=admin_headers, json=paid_body, timeout=10
        )
        assert pr2.status_code in (200, 201), pr2.text
        TestFreeEnrolmentRegression.program_id_paid = pr2.json()["id"]
        yield
        # Teardown: soft delete both programs
        for pid in (
            TestFreeEnrolmentRegression.program_id,
            TestFreeEnrolmentRegression.program_id_paid,
        ):
            requests.delete(f"{API}/programs/admin/{pid}", headers=admin_headers, timeout=10)

    def test_free_enrol_unauthenticated_401(self):
        r = requests.post(
            f"{API}/programs/{self.program_id}/enrol-free", timeout=10
        )
        assert r.status_code in (401, 403), f"Expected auth error, got {r.status_code}"

    def test_free_enrol_on_paid_program_400(self, user_headers):
        r = requests.post(
            f"{API}/programs/{self.program_id_paid}/enrol-free",
            headers=user_headers,
            timeout=10,
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:200]}"

    def test_free_enrol_success(self, user_headers):
        r = requests.post(
            f"{API}/programs/{self.program_id}/enrol-free",
            headers=user_headers,
            timeout=10,
        )
        # 201 first time, 409 if already enrolled from a previous run
        assert r.status_code in (201, 409), f"Got {r.status_code}: {r.text[:200]}"
        if r.status_code == 201:
            data = r.json()
            assert data["program_id"] == self.program_id
            assert data["source"] == "free"
            assert data["status"] == "active"

        # Verify enrolment persists via GET /programs/me/enrolments
        g = requests.get(
            f"{API}/programs/me/enrolments", headers=user_headers, timeout=10
        )
        assert g.status_code == 200
        items = g.json()["items"]
        assert any(it["program_id"] == self.program_id for it in items)


# =========================================================================
# 4) One-time Razorpay flow regression (mock mode)
# =========================================================================
def _flip_mock_mode(new_value: str) -> bool:
    """Flip RAZORPAY_MOCK_MODE in backend/.env and restart backend. Returns success."""
    env_path = "/app/backend/.env"
    with open(env_path, "r") as f:
        lines = f.readlines()
    changed = False
    for i, line in enumerate(lines):
        if line.startswith("RAZORPAY_MOCK_MODE="):
            lines[i] = f"RAZORPAY_MOCK_MODE={new_value}\n"
            changed = True
            break
    if not changed:
        lines.append(f"RAZORPAY_MOCK_MODE={new_value}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)
    # restart backend via supervisor
    os.system("sudo supervisorctl restart backend >/dev/null 2>&1")
    # Wait for backend to come back up
    for _ in range(30):
        try:
            r = requests.get(f"{API}/payments/config", timeout=3)
            if r.status_code in (200, 401, 403):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


class TestOneTimePaymentRegression:
    program_id = None
    original_mock_mode = None

    @pytest.fixture(scope="class", autouse=True)
    def _setup_mock_mode(self, admin_headers):
        # Read current mock mode
        with open("/app/backend/.env", "r") as f:
            for line in f:
                if line.startswith("RAZORPAY_MOCK_MODE="):
                    TestOneTimePaymentRegression.original_mock_mode = line.split(
                        "=", 1
                    )[1].strip()
                    break
        # Flip to true
        assert _flip_mock_mode("true"), "Failed to flip to mock mode"

        # Re-login admin (token may still work; JWT stateless)
        # Create a one-time program
        cat_body = {
            "name": "TEST_iter29_cat_pay",
            "slug": f"test-iter29-catp-{uuid.uuid4().hex[:6]}",
            "order_index": 99,
        }
        cr = requests.post(
            f"{API}/categories/admin", headers=admin_headers, json=cat_body, timeout=10
        )
        assert cr.status_code in (200, 201), cr.text
        cat_id = cr.json()["id"]

        pr = requests.post(
            f"{API}/programs/admin",
            headers=admin_headers,
            json={
                "name": "TEST_iter29_onetime_pay",
                "slug": f"test-iter29-payot-{uuid.uuid4().hex[:6]}",
                "price": 199,
                "validity_days": 30,
                "category_id": cat_id,
                "payment_type": "one_time",
            },
            timeout=10,
        )
        assert pr.status_code in (200, 201), pr.text
        TestOneTimePaymentRegression.program_id = pr.json()["id"]

        yield

        # Teardown: soft-delete program, restore mock mode
        requests.delete(
            f"{API}/programs/admin/{TestOneTimePaymentRegression.program_id}",
            headers=admin_headers,
            timeout=10,
        )
        _flip_mock_mode(TestOneTimePaymentRegression.original_mock_mode or "false")

    def test_create_order_mock(self, user_headers):
        r = requests.post(
            f"{API}/payments/order",
            headers=user_headers,
            json={"program_id": self.program_id},
            timeout=15,
        )
        assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "order_id" in data
        assert data["order_id"].startswith("mock_ord_") or data.get("is_mock") is True
        # Save order_id for verify step
        TestOneTimePaymentRegression._last_order_id = data["order_id"]

    def test_verify_payment_mock(self, user_headers):
        order_id = getattr(TestOneTimePaymentRegression, "_last_order_id", None)
        assert order_id, "No order id from previous test"
        payload = {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{order_id}",
        }
        r = requests.post(
            f"{API}/payments/verify",
            headers=user_headers,
            json=payload,
            timeout=15,
        )
        assert r.status_code in (200, 201), f"{r.status_code}: {r.text[:400]}"
        data = r.json()
        assert "purchase_id" in data
        assert "invoice_number" in data

        # Verify purchase persisted
        me = requests.get(
            f"{API}/payments/me", headers=user_headers, timeout=10
        )
        assert me.status_code == 200
        items = me.json().get("items", [])
        assert any(
            p.get("id") == data["purchase_id"] for p in items
        ), "Purchase not persisted"


# =========================================================================
# 5) Admin program creation with payment_type=subscription
# =========================================================================
class TestAdminProgramPaymentType:
    def test_create_free_program(self, admin_headers):
        cat = requests.post(
            f"{API}/categories/admin",
            headers=admin_headers,
            json={
                "name": "TEST_iter29_ptype_free",
                "slug": f"test-iter29-ptypef-{uuid.uuid4().hex[:6]}",
                "order_index": 99,
            },
            timeout=10,
        )
        cat_id = cat.json()["id"]
        r = requests.post(
            f"{API}/programs/admin",
            headers=admin_headers,
            json={
                "name": "TEST_iter29_ptype_free_prog",
                "slug": f"test-iter29-ptypefp-{uuid.uuid4().hex[:6]}",
                "price": 0,
                "validity_days": 30,
                "category_id": cat_id,
                "payment_type": "free",
            },
            timeout=10,
        )
        assert r.status_code in (200, 201), r.text
        requests.delete(
            f"{API}/programs/admin/{r.json()['id']}", headers=admin_headers, timeout=10
        )

    def test_create_one_time_program(self, admin_headers):
        cat = requests.post(
            f"{API}/categories/admin",
            headers=admin_headers,
            json={
                "name": "TEST_iter29_ptype_ot",
                "slug": f"test-iter29-ptypeot-{uuid.uuid4().hex[:6]}",
                "order_index": 99,
            },
            timeout=10,
        )
        cat_id = cat.json()["id"]
        r = requests.post(
            f"{API}/programs/admin",
            headers=admin_headers,
            json={
                "name": "TEST_iter29_ptype_ot_prog",
                "slug": f"test-iter29-ptypeotp-{uuid.uuid4().hex[:6]}",
                "price": 299,
                "validity_days": 30,
                "category_id": cat_id,
                "payment_type": "one_time",
            },
            timeout=10,
        )
        assert r.status_code in (200, 201), r.text
        requests.delete(
            f"{API}/programs/admin/{r.json()['id']}", headers=admin_headers, timeout=10
        )

    def test_create_subscription_program_behavior(self, admin_headers):
        """Documents what happens with payment_type=subscription.
        Either accepted-then-coerced or rejected (422) is acceptable per spec."""
        cat = requests.post(
            f"{API}/categories/admin",
            headers=admin_headers,
            json={
                "name": "TEST_iter29_ptype_sub",
                "slug": f"test-iter29-ptypesub-{uuid.uuid4().hex[:6]}",
                "order_index": 99,
            },
            timeout=10,
        )
        cat_id = cat.json()["id"]
        r = requests.post(
            f"{API}/programs/admin",
            headers=admin_headers,
            json={
                "name": "TEST_iter29_ptype_sub_prog",
                "slug": f"test-iter29-ptypesubp-{uuid.uuid4().hex[:6]}",
                "price": 499,
                "validity_days": 30,
                "category_id": cat_id,
                "payment_type": "subscription",
                "subscription_frequency": "monthly",
            },
            timeout=10,
        )
        # Either 422 (rejected) or 201 (silently accepted for legacy)
        assert r.status_code in (201, 200, 400, 422), f"Unexpected status: {r.status_code}: {r.text[:200]}"
        print(
            f"\n[NOTE] payment_type='subscription' response: {r.status_code} — "
            f"{'rejected' if r.status_code in (400, 422) else 'accepted'}"
        )
        if r.status_code in (200, 201):
            pid = r.json().get("id")
            if pid:
                requests.delete(
                    f"{API}/programs/admin/{pid}", headers=admin_headers, timeout=10
                )
