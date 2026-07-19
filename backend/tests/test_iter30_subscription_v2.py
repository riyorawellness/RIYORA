"""Iter30 — Razorpay Subscription v2: Quarterly + cycle math + friendly errors.

Extends iter27 coverage with the 4th frequency (quarterly) and adds the
webhook cycle-math + _friendly_razorpay_error mapping assertions.

Prerequisites:
- RAZORPAY_MOCK_MODE=true in /app/backend/.env
- Admin: 9999999999 / Admin@12345
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL must be set")
API = f"{BASE_URL}/api"


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": "9999999999", "password": "Admin@12345"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    tok = r.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def category(admin_headers):
    slug = f"iter30-{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{API}/categories/admin",
        headers=admin_headers,
        json={"name": f"TEST_iter30_{slug}", "slug": slug, "order_index": 99},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_program(admin_headers, category_id, name_suffix, payment_type,
                    subscription_frequency=None, price=499.0):
    slug_base = name_suffix.lower().replace("_", "-")
    payload = {
        "name": f"TEST_iter30_{name_suffix}",
        "slug": f"test-iter30-{slug_base}-{uuid.uuid4().hex[:5]}",
        "price": price,
        "validity_days": 30,
        "category_id": category_id,
        "payment_type": payment_type,
        "is_active": True,
        "gst_percent": 0,
    }
    if subscription_frequency:
        payload["subscription_frequency"] = subscription_frequency
    r = requests.post(f"{API}/programs/admin", headers=admin_headers,
                      json=payload, timeout=15)
    return r


def _mkdummy(admin_headers, label):
    payload = {
        "full_name": f"TEST iter30 {label}",
        "email": f"test_iter30_{label}_{uuid.uuid4().hex[:6]}@example.com",
        "mobile": f"90000{uuid.uuid4().hex[:5]}",
        "password": "tester123",
    }
    r = requests.post(f"{API}/admin/users/dummy", headers=admin_headers,
                      json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    return payload


def _login_email(email, password="tester123"):
    r = requests.post(f"{API}/auth/login",
                      json={"email": email, "password": password},
                      timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["tokens"]["access_token"]


def _user_headers(admin_headers, label):
    p = _mkdummy(admin_headers, label)
    tok = _login_email(p["email"])
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# =============================================================================
# 1. Admin program creation with each of 4 frequencies + rejection of unknown
# =============================================================================


class TestAdminProgramFrequency:
    @pytest.mark.parametrize("freq", ["monthly", "quarterly", "half_yearly", "yearly"])
    def test_create_subscription_program_each_frequency(self, admin_headers, category, freq):
        r = _create_program(admin_headers, category["id"], f"F_{freq}",
                            "subscription", freq, price=299.0)
        assert r.status_code in (200, 201), r.text
        data = r.json()
        assert data["payment_type"] == "subscription"
        assert data["subscription_frequency"] == freq

        # GET verifies persistence (admin-scoped list to avoid auth on public GET)
        rg = requests.get(f"{API}/programs/{data['id']}", headers=admin_headers, timeout=15)
        assert rg.status_code == 200, rg.text
        gdata = rg.json()
        assert gdata["subscription_frequency"] == freq

    def test_unknown_frequency_rejected(self, admin_headers, category):
        r = _create_program(admin_headers, category["id"], "Bad",
                            "subscription", "weekly", price=199.0)
        assert r.status_code == 422, r.text


# =============================================================================
# 2. /subscription/init for each of 4 frequencies (mock mode)
# =============================================================================


class TestInitEachFrequency:
    @pytest.mark.parametrize("freq", ["monthly", "quarterly", "half_yearly", "yearly"])
    def test_init_mock(self, admin_headers, category, freq):
        prog = _create_program(admin_headers, category["id"], f"Init_{freq}",
                               "subscription", freq, price=299.0).json()
        h = _user_headers(admin_headers, f"init_{freq}")
        r = requests.post(f"{API}/payments/subscription/init",
                          headers=h, json={"program_id": prog["id"]},
                          timeout=20)
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["subscription_id"].startswith("mock_sub_")
        assert d["plan_id"].startswith("mock_plan_")
        assert d["is_mock"] is True
        assert d["status"] == "created"
        assert d["program"]["subscription_frequency"] == freq


# =============================================================================
# 3. Cycle math: verify creates purchase with correct validity + total_count
# =============================================================================


class TestCycleMath:
    @pytest.mark.parametrize("freq,days,total_count", [
        ("monthly", 30, 60),
        ("quarterly", 90, 40),
        ("half_yearly", 180, 20),
        ("yearly", 365, 10),
    ])
    def test_verify_cycle_days_and_total_count(self, admin_headers, category,
                                                freq, days, total_count):
        prog = _create_program(admin_headers, category["id"], f"CM_{freq}",
                               "subscription", freq, price=199.0).json()
        h = _user_headers(admin_headers, f"cm_{freq}")
        r = requests.post(f"{API}/payments/subscription/init",
                          headers=h, json={"program_id": prog["id"]},
                          timeout=20)
        assert r.status_code == 201, r.text
        sid = r.json()["subscription_id"]

        # Verify → materialises first cycle purchase
        rv = requests.post(f"{API}/payments/subscription/{sid}/verify",
                           headers=h, timeout=20)
        assert rv.status_code == 200, rv.text
        vd = rv.json()
        assert vd["purchase_id"]
        # cycle days assertion: parse ISO purchase + expiry
        from datetime import datetime
        exp = datetime.fromisoformat(vd["expiry_date"].replace("Z", "+00:00"))
        pur = datetime.fromisoformat(vd["purchase_date"].replace("Z", "+00:00")) \
            if vd.get("purchase_date") else None
        if pur:
            delta_days = (exp - pur).days
            assert delta_days == days, f"{freq}: expected {days}d, got {delta_days}d"

        # total_count from /subscription/me
        rme = requests.get(f"{API}/payments/subscription/me", headers=h, timeout=15)
        assert rme.status_code == 200
        items = [s for s in rme.json()["items"] if s["subscription_id"] == sid]
        assert items
        assert items[0]["total_count"] == total_count


# =============================================================================
# 4. Race-safe reuse + fresh sid after cancel
# =============================================================================


class TestReuseAndFreshAfterCancel:
    def test_reuse_then_fresh_after_cancel(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "ReuseCancel",
                               "subscription", "quarterly", price=299.0).json()
        h = _user_headers(admin_headers, "reuse_cancel")

        r1 = requests.post(f"{API}/payments/subscription/init",
                          headers=h, json={"program_id": prog["id"]}, timeout=20)
        assert r1.status_code == 201
        sid1 = r1.json()["subscription_id"]

        r2 = requests.post(f"{API}/payments/subscription/init",
                          headers=h, json={"program_id": prog["id"]}, timeout=20)
        assert r2.status_code == 201
        assert r2.json()["subscription_id"] == sid1
        assert r2.json()["reused"] is True

        # Cancel while created → immediate
        rc = requests.post(f"{API}/payments/subscription/{sid1}/cancel",
                           headers=h, timeout=20)
        assert rc.status_code == 200
        assert rc.json()["status"] == "cancelled"
        assert rc.json()["cancel_at_cycle_end"] is False

        # Fresh init after cancel
        r3 = requests.post(f"{API}/payments/subscription/init",
                          headers=h, json={"program_id": prog["id"]}, timeout=20)
        assert r3.status_code == 201
        assert r3.json()["subscription_id"] != sid1
        assert r3.json()["reused"] is False


# =============================================================================
# 5. Cancel while active → cancel_at_cycle_end=True
# =============================================================================


class TestCancelActive:
    def test_active_cancel_uses_cycle_end(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "CancelActive",
                               "subscription", "monthly", price=199.0).json()
        h = _user_headers(admin_headers, "cancel_active")
        r = requests.post(f"{API}/payments/subscription/init",
                         headers=h, json={"program_id": prog["id"]}, timeout=20)
        sid = r.json()["subscription_id"]

        # verify → status becomes active
        rv = requests.post(f"{API}/payments/subscription/{sid}/verify",
                          headers=h, timeout=20)
        assert rv.status_code == 200

        rc = requests.post(f"{API}/payments/subscription/{sid}/cancel",
                          headers=h, timeout=20)
        assert rc.status_code == 200, rc.text
        d = rc.json()
        # active mandate → cycle-end cancel
        assert d["cancel_at_cycle_end"] is True


# =============================================================================
# 6. Webhook subscription.charged idempotency + cycle days
# =============================================================================


class TestWebhookCharged:
    def test_webhook_creates_and_is_idempotent(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "WHCharged",
                               "subscription", "quarterly", price=299.0).json()
        h = _user_headers(admin_headers, "wh_charged")
        r = requests.post(f"{API}/payments/subscription/init",
                         headers=h, json={"program_id": prog["id"]}, timeout=20)
        sid = r.json()["subscription_id"]

        payment_id = f"pay_TEST30_{uuid.uuid4().hex[:12]}"
        body = {
            "event": "subscription.charged",
            "payload": {
                "subscription": {"entity": {"id": sid, "status": "active",
                                            "paid_count": 3,
                                            "current_start": 1000000000,
                                            "current_end": 1002592000}},
                "payment": {"entity": {"id": payment_id, "amount": 29900,
                                       "status": "captured", "recurring": True}},
            },
        }
        headers = {"X-Razorpay-Signature": "mock_sig_xyz",
                   "Content-Type": "application/json"}
        r1 = requests.post(f"{API}/payments/webhook",
                           headers=headers, json=body, timeout=20)
        assert r1.status_code == 200, r1.text
        time.sleep(1)

        rs = requests.get(f"{API}/programs/{prog['id']}/status",
                          headers=h, timeout=15)
        assert rs.status_code == 200
        ap = rs.json().get("active_purchase") or {}
        assert ap.get("razorpay_payment_id") == payment_id
        assert ap.get("source") == "razorpay_subscription"
        assert ap.get("is_subscription") is True

        # cycle days for quarterly = 90
        from datetime import datetime
        exp = datetime.fromisoformat(ap["expiry_date"].replace("Z", "+00:00"))
        pur = datetime.fromisoformat(ap["purchase_date"].replace("Z", "+00:00"))
        assert (exp - pur).days == 90

        # Idempotent replay
        r2 = requests.post(f"{API}/payments/webhook",
                          headers=headers, json=body, timeout=20)
        assert r2.status_code == 200
        time.sleep(1)

        rme = requests.get(f"{API}/payments/me", headers=h, timeout=15)
        purchases = [p for p in rme.json()["items"]
                     if p.get("razorpay_payment_id") == payment_id]
        assert len(purchases) == 1, f"Expected 1, got {len(purchases)}"


# =============================================================================
# 7. Friendly error mapping
# =============================================================================


class TestFriendlyError:
    def test_helper_maps_not_authorized(self):
        """Inspect _friendly_razorpay_error source to confirm mapping exists."""
        src_path = "/app/backend/app/routes/enrolments.py"
        with open(src_path) as f:
            src = f.read()
        # Function must exist
        assert "def _friendly_razorpay_error" in src
        # Mapping must include the sub-support email and friendly text
        assert "sub-support@razorpay.com" in src
        assert "not authorized" in src or "not enabled" in src or "not activated" in src
        # Verify it's called in the /init route (raises 502)
        assert "502, _friendly_razorpay_error" in src or "raise HTTPException(502, _friendly_razorpay_error" in src


# =============================================================================
# 8. Webhook coverage endpoint
# =============================================================================


class TestWebhookCoverage:
    def test_returns_9_events(self, admin_headers):
        r = requests.get(f"{API}/admin/qa/live-check/webhook-coverage",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        req_events = data.get("required_events") or []
        assert len(req_events) == 9, f"Expected 9 required events, got {len(req_events)}"
        checklist = data.get("checklist") or []
        assert len(checklist) == 9
        cats = {}
        for e in checklist:
            cats.setdefault(e.get("category"), 0)
            cats[e.get("category")] += 1
        assert cats.get("one_time") == 3, f"one_time count: {cats.get('one_time')}"
        assert cats.get("subscription") == 6, f"subscription count: {cats.get('subscription')}"


# =============================================================================
# 9. Regression: one-time still works
# =============================================================================


class TestRegressionOneTime:
    def test_one_time_order_and_verify(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "OT",
                               "one_time", price=399.0).json()
        h = _user_headers(admin_headers, "ot_reg")
        r_o = requests.post(f"{API}/payments/order", headers=h,
                            json={"program_id": prog["id"]}, timeout=15)
        assert r_o.status_code == 201, r_o.text
        order = r_o.json()
        assert order["order_id"].startswith("mock_ord_")
        r_v = requests.post(f"{API}/payments/verify", headers=h, json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": f"pay_mock_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{order['order_id']}",
        }, timeout=15)
        assert r_v.status_code == 200
        assert r_v.json()["success"] is True

    def test_free_enrol(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "FR",
                               "free", price=0.0).json()
        h = _user_headers(admin_headers, "free_reg")
        r = requests.post(f"{API}/programs/{prog['id']}/enrol-free",
                          headers=h, timeout=15)
        assert r.status_code == 201
        assert r.json()["status"] == "active"
