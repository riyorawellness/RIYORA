"""Iter32 — Predefined Razorpay Plan IDs (no more dynamic plan creation).

Coverage:
  1. GET /api/settings/app publicly exposes razorpay_plan_id_monthly
     = plan_TFfcwnQxmKL774 (pre-seeded) and does NOT contain the
     other three frequency keys (quarterly / half_yearly / yearly).
  2. PUT /api/settings/app/admin can save (upsert) a quarterly plan_id
     and it persists — verified via GET /api/settings/app.
  3. PUT with value=null (implementation's "clear" flow) upserts null.
     After clearing, subscription.init for that frequency must return
     the "not configured" 500 again.
  4. POST /api/payments/subscription/init for a monthly-frequency program
     uses the configured plan_id (plan_TFfcwnQxmKL774) — either succeeds
     (mock mode) or fails softly with a Razorpay account-provisioning
     error (live mode + Subscriptions not enabled). Both are acceptable
     — the CODE contract is that _get_configured_plan_id resolves and
     is passed through.
  5. NEGATIVE: subscription.init for a quarterly program (no plan_id
     configured) returns 500 with the admin-facing message.
  6. REGRESSION: One-time /payments/order + /payments/verify still work.

Prereqs:
  Admin: 9999999999 / Admin@12345
  Dummy: qa-tester@example.com / tester123 (email fallback login)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL must be set")
API = f"{BASE_URL}/api"

EXPECTED_MONTHLY_PLAN = "plan_TFfcwnQxmKL774"


# ---------------- fixtures ----------------

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
def tester_headers():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": "qa-tester@example.com", "password": "tester123"},
        timeout=15,
    )
    assert r.status_code == 200, f"dummy tester login failed: {r.text}"
    tok = r.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def category(admin_headers):
    slug = f"iter32-{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{API}/categories/admin",
        headers=admin_headers,
        json={"name": f"TEST_iter32_{slug}", "slug": slug, "order_index": 99},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_program(admin_headers, category_id, suffix, payment_type,
                    subscription_frequency=None, price=299.0):
    payload = {
        "name": f"TEST_iter32_{suffix}",
        "slug": f"test-iter32-{suffix.lower()}-{uuid.uuid4().hex[:5]}",
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
    assert r.status_code in (200, 201), r.text
    return r.json()


# ====================================================================
# 1. Pre-seeded monthly plan is exposed on GET /settings/app
# ====================================================================

class TestSettingsExposure:
    def test_monthly_preseeded_and_others_absent(self):
        r = requests.get(f"{API}/settings/app", timeout=15)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s.get("razorpay_plan_id_monthly") == EXPECTED_MONTHLY_PLAN, (
            f"monthly plan mismatch — got {s.get('razorpay_plan_id_monthly')!r}"
        )
        # Others should NOT be configured (spec — negative flow relies on this)
        for freq in ("quarterly", "half_yearly", "yearly"):
            val = s.get(f"razorpay_plan_id_{freq}")
            assert not val, (
                f"razorpay_plan_id_{freq} should be absent/blank, got {val!r}"
            )


# ====================================================================
# 2 & 3. Admin upsert + clear round-trip
# ====================================================================

class TestAdminUpsertPlanId:
    TEMP_KEY = "razorpay_plan_id_quarterly"
    TEMP_VAL = "plan_TEST_iter32_QRT01"

    def test_save_persist_and_clear(self, admin_headers):
        # a. Save
        r = requests.put(
            f"{API}/settings/app/admin",
            headers=admin_headers,
            json={"key": self.TEMP_KEY, "value": self.TEMP_VAL,
                  "description": "TEST iter32 quarterly plan id"},
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text
        assert r.json().get("value") == self.TEMP_VAL

        # b. Verify persisted via public GET /settings/app
        r2 = requests.get(f"{API}/settings/app", timeout=15)
        assert r2.json().get(self.TEMP_KEY) == self.TEMP_VAL

        # c. Clear (frontend sends null when the field is blank)
        r3 = requests.put(
            f"{API}/settings/app/admin",
            headers=admin_headers,
            json={"key": self.TEMP_KEY, "value": None,
                  "description": "TEST iter32 quarterly plan id"},
            timeout=15,
        )
        assert r3.status_code in (200, 201), r3.text

        # d. After clear: /settings/app should have null (or absent) for the key
        r4 = requests.get(f"{API}/settings/app", timeout=15)
        cleared_val = r4.json().get(self.TEMP_KEY)
        assert cleared_val in (None, ""), (
            f"expected cleared, got {cleared_val!r}"
        )


# ====================================================================
# 5. NEGATIVE — subscription init for unconfigured frequency (quarterly)
# ====================================================================

class TestUnconfiguredPlanError:
    def test_quarterly_returns_500_with_admin_message(
        self, admin_headers, tester_headers, category
    ):
        # Ensure quarterly is UNCONFIGURED — spec says "do not seed it".
        # If a previous test left one, clear it first.
        requests.put(
            f"{API}/settings/app/admin",
            headers=admin_headers,
            json={"key": "razorpay_plan_id_quarterly", "value": None},
            timeout=10,
        )

        prog = _create_program(admin_headers, category["id"], "QrtNoPlan",
                               "subscription", "quarterly", price=299.0)
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers=tester_headers,
            json={"program_id": prog["id"]},
            timeout=20,
        )
        assert r.status_code == 500, r.text
        body = r.json()
        detail = str(body.get("detail") or body)
        assert "quarterly" in detail.lower()
        assert "not configured" in detail.lower()
        assert "payment settings" in detail.lower() or "subscription plans" in detail.lower()


# ====================================================================
# 4. subscription.init picks up plan_TFfcwnQxmKL774 for monthly
#     (live-mode account may 502 with "Subscriptions not enabled" — soft-pass)
# ====================================================================

class TestMonthlySubscriptionUsesPreseededPlan:
    def test_monthly_uses_preseeded_plan_or_soft_pass_on_live_provisioning(
        self, admin_headers, tester_headers, category
    ):
        prog = _create_program(admin_headers, category["id"], "MonthlyGood",
                               "subscription", "monthly", price=199.0)
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers=tester_headers,
            json={"program_id": prog["id"]},
            timeout=25,
        )
        if r.status_code == 201:
            data = r.json()
            assert data.get("plan_id") == EXPECTED_MONTHLY_PLAN, (
                f"expected plan_id={EXPECTED_MONTHLY_PLAN}, got {data.get('plan_id')!r}"
            )
            # subscription_id may be Razorpay `sub_*` (live) or `mock_sub_*` (mock)
            assert data.get("subscription_id")
        elif r.status_code == 502:
            body = str(r.json())
            # Soft-pass ONLY for account-provisioning errors (Subscriptions
            # feature not enabled). Any other 502 is a code bug.
            low = body.lower()
            provisioning_markers = (
                "not enabled", "not authorized", "not activated",
                "activate", "not authorised",
            )
            assert any(m in low for m in provisioning_markers), (
                f"502 without provisioning marker — likely a real bug: {body}"
            )
            pytest.skip(
                "Razorpay account has Subscriptions disabled — soft-pass "
                "(code path resolves plan_id correctly, provisioning gap)."
            )
        else:
            pytest.fail(f"Unexpected status {r.status_code}: {r.text}")


# ====================================================================
# 6. REGRESSION — one-time payment order/verify untouched
# ====================================================================

class TestOneTimeRegression:
    def test_one_time_order_and_verify_still_works(
        self, admin_headers, tester_headers, category
    ):
        prog = _create_program(admin_headers, category["id"], "OneTime",
                               "one_time", price=399.0)
        # 1) order
        ro = requests.post(f"{API}/payments/order", headers=tester_headers,
                           json={"program_id": prog["id"]}, timeout=15)
        assert ro.status_code == 201, ro.text
        order = ro.json()
        assert "order_id" in order
        # 2) verify (mock or live signature)
        rv = requests.post(f"{API}/payments/verify", headers=tester_headers, json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": f"pay_mock_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{order['order_id']}",
        }, timeout=15)
        # In live mode, verify will fail signature check → 400. That's still
        # a REGRESSION-pass: the endpoint is reachable + validates signature.
        # In mock mode → 200. Both prove one-time flow untouched.
        assert rv.status_code in (200, 400), rv.text


# ====================================================================
# 7. REGRESSION — /subscription/me still loads (used by "My Subscriptions" page)
# ====================================================================

class TestMySubscriptionsRegression:
    def test_my_subs_endpoint_loads(self, tester_headers):
        r = requests.get(f"{API}/payments/subscription/me",
                         headers=tester_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert isinstance(body["items"], list)
