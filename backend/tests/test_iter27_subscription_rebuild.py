"""Iter27 — Subscription (Razorpay AutoPay/UPI mandate) rebuild tests.

Prerequisites:
- RAZORPAY_MOCK_MODE=true in /app/backend/.env
- Admin: 9999999999 / Admin@12345 (seeded)

Test coverage:
- POST /api/payments/subscription/init (success/reuse/404/400/409)
- POST /api/payments/subscription/{sid}/verify (mock materialise + idempotent)
- GET /api/programs/{id}/status (has_access=true + active_purchase populated)
- POST /api/payments/subscription/{sid}/cancel (immediate for created state)
- POST /api/payments/webhook (subscription.charged idempotent + status mirror)
- Regression: free enrol + one-time /order + /verify still work
- total_count safety: monthly=60 / half_yearly=20 / yearly=10
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
API = f"{BASE_URL}/api"

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": "9999999999", "password": "Admin@12345"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def category(admin_headers):
    slug = f"iter27-{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{API}/categories/admin",
        headers=admin_headers,
        json={"name": f"TEST_iter27_{slug}", "slug": slug, "order_index": 99},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_program(admin_headers, category_id, name_suffix, payment_type,
                    subscription_frequency=None, price=499.0):
    slug_base = name_suffix.lower().replace("_", "-")
    payload = {
        "name": f"TEST_iter27_{name_suffix}",
        "slug": f"test-iter27-{slug_base}-{uuid.uuid4().hex[:5]}",
        "price": price,
        "validity_days": 30,
        "category_id": category_id,
        "payment_type": payment_type,
        "is_active": True,
        "gst_percent": 0,
    }
    if subscription_frequency:
        payload["subscription_frequency"] = subscription_frequency
    r = requests.post(f"{API}/programs/admin", headers=admin_headers, json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    return r.json()


@pytest.fixture(scope="module")
def sub_program_monthly(admin_headers, category):
    return _create_program(admin_headers, category["id"], "SubMonthly",
                           "subscription", "monthly", price=499.0)


@pytest.fixture(scope="module")
def sub_program_yearly(admin_headers, category):
    return _create_program(admin_headers, category["id"], "SubYearly",
                           "subscription", "yearly", price=4999.0)


@pytest.fixture(scope="module")
def sub_program_half_yearly(admin_headers, category):
    return _create_program(admin_headers, category["id"], "SubHalf",
                           "subscription", "half_yearly", price=2499.0)


@pytest.fixture(scope="module")
def free_program(admin_headers, category):
    return _create_program(admin_headers, category["id"], "Free",
                           "free", price=0.0)


@pytest.fixture(scope="module")
def onetime_program(admin_headers, category):
    return _create_program(admin_headers, category["id"], "OneTime",
                           "one_time", price=399.0)


def _mkdummy(admin_headers, label):
    payload = {
        "full_name": f"TEST iter27 {label}",
        "email": f"test_iter27_{label}_{uuid.uuid4().hex[:6]}@example.com",
        "mobile": f"90000{uuid.uuid4().hex[:5]}",
        "password": "tester123",
    }
    r = requests.post(f"{API}/admin/users/dummy", headers=admin_headers, json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    return payload, r.json()


def _login_email(email, password="tester123"):
    r = requests.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="module")
def user_a(admin_headers):
    payload, user = _mkdummy(admin_headers, "userA")
    tok = _login_email(payload["email"], payload["password"])
    return {"headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
            "membership_id": user.get("membership_id") or (user.get("user") or {}).get("membership_id"),
            "email": payload["email"]}


@pytest.fixture(scope="module")
def user_b(admin_headers):
    payload, user = _mkdummy(admin_headers, "userB")
    tok = _login_email(payload["email"], payload["password"])
    return {"headers": {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
            "membership_id": user.get("membership_id") or (user.get("user") or {}).get("membership_id"),
            "email": payload["email"]}


# -----------------------------------------------------------------------------
# Subscription init: happy path + is_mock=true in mock mode
# -----------------------------------------------------------------------------


class TestSubscriptionInit:
    def test_init_success_returns_all_fields(self, user_a, sub_program_monthly):
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers=user_a["headers"],
            json={"program_id": sub_program_monthly["id"]},
            timeout=20,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["subscription_id"].startswith("mock_sub_")
        assert data["plan_id"].startswith("mock_plan_")
        assert "key_id" in data
        assert data["is_mock"] is True
        assert data["reused"] is False
        assert "breakdown" in data
        assert data["breakdown"]["total"] == 499.0  # gst=0
        assert data["program"]["subscription_frequency"] == "monthly"

    def test_init_non_subscription_returns_400(self, user_a, onetime_program):
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers=user_a["headers"],
            json={"program_id": onetime_program["id"]},
            timeout=15,
        )
        assert r.status_code == 400
        assert "not a subscription" in r.text.lower()

    def test_init_nonexistent_program_returns_404(self, user_a):
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers=user_a["headers"],
            json={"program_id": "does-not-exist-" + uuid.uuid4().hex},
            timeout=15,
        )
        assert r.status_code == 404

    def test_init_unauthenticated_returns_401(self, sub_program_monthly):
        r = requests.post(
            f"{API}/payments/subscription/init",
            json={"program_id": sub_program_monthly["id"]},
            timeout=15,
        )
        assert r.status_code == 401


# -----------------------------------------------------------------------------
# Race-safe reuse: 2nd init within 60min returns same subscription_id
# -----------------------------------------------------------------------------


class TestSubscriptionReuse:
    def test_second_init_reuses_same_subscription_id(self, user_b, sub_program_yearly):
        # First init
        r1 = requests.post(
            f"{API}/payments/subscription/init",
            headers=user_b["headers"],
            json={"program_id": sub_program_yearly["id"]},
            timeout=20,
        )
        assert r1.status_code == 201
        first_sid = r1.json()["subscription_id"]

        # Second init immediately — must reuse
        r2 = requests.post(
            f"{API}/payments/subscription/init",
            headers=user_b["headers"],
            json={"program_id": sub_program_yearly["id"]},
            timeout=20,
        )
        assert r2.status_code == 201
        data2 = r2.json()
        assert data2["subscription_id"] == first_sid
        assert data2["reused"] is True


# -----------------------------------------------------------------------------
# Verify → materialise purchase + idempotent + status
# -----------------------------------------------------------------------------


class TestSubscriptionVerify:
    def test_verify_materialises_purchase_and_grants_access(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "VerifyProg",
                               "subscription", "monthly", price=299.0)
        payload, _ = _mkdummy(admin_headers, "verify_user")
        tok = _login_email(payload["email"])
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        r = requests.post(
            f"{API}/payments/subscription/init",
            headers=h, json={"program_id": prog["id"]}, timeout=20,
        )
        assert r.status_code == 201
        sid = r.json()["subscription_id"]

        # First verify — should materialise a purchase
        r_v = requests.post(f"{API}/payments/subscription/{sid}/verify",
                            headers=h, timeout=20)
        assert r_v.status_code == 200, r_v.text
        v_data = r_v.json()
        assert v_data["purchase_id"] is not None
        assert v_data["expiry_date"] is not None
        first_purchase_id = v_data["purchase_id"]
        assert v_data["status"] == "active"

        # Second verify — idempotent, returns same purchase_id
        r_v2 = requests.post(f"{API}/payments/subscription/{sid}/verify",
                             headers=h, timeout=20)
        assert r_v2.status_code == 200
        assert r_v2.json()["purchase_id"] == first_purchase_id

        # Program status → has_access=true with active_purchase.expiry_date
        r_s = requests.get(f"{API}/programs/{prog['id']}/status",
                           headers=h, timeout=15)
        assert r_s.status_code == 200
        s = r_s.json()
        assert s["has_access"] is True
        assert s["active_purchase"] is not None
        assert s["active_purchase"].get("expiry_date")
        assert s["active_purchase"].get("is_subscription") is True
        assert s["active_purchase"].get("source") == "razorpay_subscription"


# -----------------------------------------------------------------------------
# Cancel — pending mandate → immediate cancel, then re-init returns FRESH sid
# -----------------------------------------------------------------------------


class TestSubscriptionCancel:
    def test_cancel_created_state_uses_immediate(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "CancelProg",
                               "subscription", "monthly", price=299.0)
        payload, _ = _mkdummy(admin_headers, "cancel_user")
        tok = _login_email(payload["email"])
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        r = requests.post(f"{API}/payments/subscription/init",
                         headers=h, json={"program_id": prog["id"]}, timeout=20)
        assert r.status_code == 201
        sid_1 = r.json()["subscription_id"]
        assert r.json()["status"] == "created"

        # Cancel — mandate never authenticated → immediate (cancel_at_cycle_end=False)
        r_c = requests.post(f"{API}/payments/subscription/{sid_1}/cancel",
                            headers=h, timeout=20)
        assert r_c.status_code == 200, r_c.text
        cdata = r_c.json()
        assert cdata["status"] == "cancelled"
        assert cdata["cancel_at_cycle_end"] is False

        # Subsequent init → FRESH subscription_id
        r2 = requests.post(f"{API}/payments/subscription/init",
                          headers=h, json={"program_id": prog["id"]}, timeout=20)
        assert r2.status_code == 201
        sid_2 = r2.json()["subscription_id"]
        assert sid_2 != sid_1
        assert r2.json()["reused"] is False


# -----------------------------------------------------------------------------
# Already active access → 409 on re-subscribe
# -----------------------------------------------------------------------------


class TestSubscriptionActiveConflict:
    def test_active_purchase_blocks_new_init(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "ActiveConflict",
                               "subscription", "monthly", price=99.0)
        payload, _ = _mkdummy(admin_headers, "conflict_user")
        tok = _login_email(payload["email"])
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        r = requests.post(f"{API}/payments/subscription/init",
                         headers=h, json={"program_id": prog["id"]}, timeout=20)
        sid = r.json()["subscription_id"]
        # verify → creates active_purchase
        requests.post(f"{API}/payments/subscription/{sid}/verify",
                     headers=h, timeout=20)
        # Now init again — expected 409
        r2 = requests.post(f"{API}/payments/subscription/init",
                          headers=h, json={"program_id": prog["id"]}, timeout=15)
        assert r2.status_code == 409, r2.text


# -----------------------------------------------------------------------------
# Webhook subscription.charged: idempotent + creates purchase + fires
# -----------------------------------------------------------------------------


class TestSubscriptionWebhook:
    def test_charged_creates_purchase_and_is_idempotent(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "WebhookProg",
                               "subscription", "monthly", price=199.0)
        payload, _ = _mkdummy(admin_headers, "webhook_user")
        tok = _login_email(payload["email"])
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        r = requests.post(f"{API}/payments/subscription/init",
                         headers=h, json={"program_id": prog["id"]}, timeout=20)
        sid = r.json()["subscription_id"]

        payment_id = f"pay_TEST_{uuid.uuid4().hex[:14]}"
        webhook_body = {
            "event": "subscription.charged",
            "payload": {
                "subscription": {"entity": {"id": sid, "status": "active",
                                             "paid_count": 2,
                                             "current_start": 1000000000,
                                             "current_end": 1002592000}},
                "payment": {"entity": {"id": payment_id, "amount": 19900,
                                       "status": "captured", "recurring": True}},
            },
        }
        # 1st webhook fire — creates a purchase
        r_w = requests.post(f"{API}/payments/webhook",
                            headers={"X-Razorpay-Signature": "mock_sig_test",
                                     "Content-Type": "application/json"},
                            json=webhook_body, timeout=20)
        assert r_w.status_code == 200

        # Give async work a moment
        time.sleep(1)

        # Check: purchase exists via /programs/me/purchases (or programs/status)
        r_s = requests.get(f"{API}/programs/{prog['id']}/status", headers=h, timeout=15)
        assert r_s.status_code == 200
        assert r_s.json()["has_access"] is True
        first_purchase = r_s.json()["active_purchase"]
        assert first_purchase["razorpay_payment_id"] == payment_id
        assert first_purchase["subscription_cycle"] == 2
        assert first_purchase["source"] == "razorpay_subscription"

        # Idempotency: fire same webhook again → no duplicate purchase
        r_w2 = requests.post(f"{API}/payments/webhook",
                             headers={"X-Razorpay-Signature": "mock_sig_test",
                                      "Content-Type": "application/json"},
                             json=webhook_body, timeout=20)
        assert r_w2.status_code == 200
        time.sleep(1)

        # Check /payments/me — only 1 purchase for this subscription
        r_me = requests.get(f"{API}/payments/me", headers=h, timeout=15)
        purchases = [p for p in r_me.json()["items"]
                     if p.get("subscription_id") == sid]
        assert len(purchases) == 1, f"Expected 1 purchase, got {len(purchases)}"

    def test_cancelled_event_mirrors_status(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "WHCancel",
                               "subscription", "monthly", price=99.0)
        payload, _ = _mkdummy(admin_headers, "wh_cancel_user")
        tok = _login_email(payload["email"])
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        r = requests.post(f"{API}/payments/subscription/init",
                         headers=h, json={"program_id": prog["id"]}, timeout=20)
        sid = r.json()["subscription_id"]

        wb = {
            "event": "subscription.cancelled",
            "payload": {
                "subscription": {"entity": {"id": sid, "status": "cancelled"}},
            },
        }
        r_w = requests.post(f"{API}/payments/webhook",
                            headers={"X-Razorpay-Signature": "mock_sig_test",
                                     "Content-Type": "application/json"},
                            json=wb, timeout=15)
        assert r_w.status_code == 200

        # /payments/subscription/me should show it as cancelled
        r_me = requests.get(f"{API}/payments/subscription/me", headers=h, timeout=15)
        items = [s for s in r_me.json()["items"] if s["subscription_id"] == sid]
        assert items and items[0]["status"] == "cancelled"


# -----------------------------------------------------------------------------
# total_count safety caps
# -----------------------------------------------------------------------------


class TestTotalCountCaps:
    @pytest.mark.parametrize("freq,expected", [
        ("monthly", 60),
        ("half_yearly", 20),
        ("yearly", 10),
    ])
    def test_total_count_by_frequency(self, admin_headers, category, freq, expected):
        prog = _create_program(admin_headers, category["id"], f"TC_{freq}",
                               "subscription", freq, price=199.0)
        payload, _ = _mkdummy(admin_headers, f"tc_{freq}")
        tok = _login_email(payload["email"])
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        r = requests.post(f"{API}/payments/subscription/init",
                         headers=h, json={"program_id": prog["id"]}, timeout=20)
        assert r.status_code == 201
        sid = r.json()["subscription_id"]

        r_me = requests.get(f"{API}/payments/subscription/me", headers=h, timeout=15)
        items = [s for s in r_me.json()["items"] if s["subscription_id"] == sid]
        assert items
        assert items[0]["total_count"] == expected, (
            f"total_count for {freq}: expected {expected}, got {items[0]['total_count']}"
        )


# -----------------------------------------------------------------------------
# Regression: free enrol + one-time still work
# -----------------------------------------------------------------------------


class TestRegressionFreeAndOneTime:
    def test_free_enrol_flow(self, admin_headers, free_program):
        payload, _ = _mkdummy(admin_headers, "free_user")
        tok = _login_email(payload["email"])
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        r = requests.post(f"{API}/programs/{free_program['id']}/enrol-free",
                        headers=h, timeout=15)
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "active"
        assert r.json()["source"] == "free"

        # /status should reflect access
        rs = requests.get(f"{API}/programs/{free_program['id']}/status",
                        headers=h, timeout=15)
        assert rs.status_code == 200
        assert rs.json()["has_access"] is True

    def test_one_time_order_and_verify(self, admin_headers, onetime_program):
        payload, _ = _mkdummy(admin_headers, "ot_user")
        tok = _login_email(payload["email"])
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        r_o = requests.post(f"{API}/payments/order",
                            headers=h,
                            json={"program_id": onetime_program["id"]},
                            timeout=15)
        assert r_o.status_code == 201, r_o.text
        order = r_o.json()
        assert order["order_id"].startswith("mock_ord_")
        assert order["is_mock"] is True

        r_v = requests.post(f"{API}/payments/verify", headers=h, json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": f"pay_mock_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{order['order_id']}",
        }, timeout=15)
        assert r_v.status_code == 200, r_v.text
        assert r_v.json()["success"] is True
        assert r_v.json()["purchase_id"]
