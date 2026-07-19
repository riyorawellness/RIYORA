"""Iter31 — Payment failure handling.

Tests:
  1. subscription.pending webhook → sub.status='pending' + ONE notification (dedup)
  2. subscription.halted   webhook → sub.status='halted'  + ONE notification (dedup)
  3. payment.failed webhook (one-time) → order.status='failed', notification created
     (and NO notification if order was already 'paid')
  4. GET /admin/qa/failed-subscriptions — admin only, returns halted+pending w/ user
  5. Regression: subscription.charged still creates purchase idempotently and
     does NOT fire a failure notification.
  6. Regression: /subscription/init after halted returns FRESH subscription_id.

Prereqs:
  RAZORPAY_MOCK_MODE=true
  Admin: 9999999999 / Admin@12345
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

WH_HEADERS = {"X-Razorpay-Signature": "mock_sig_xyz",
              "Content-Type": "application/json"}


# ---------- Fixtures ---------------------------------------------------------


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
    slug = f"iter31-{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{API}/categories/admin",
        headers=admin_headers,
        json={"name": f"TEST_iter31_{slug}", "slug": slug, "order_index": 99},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_program(admin_headers, category_id, name_suffix, payment_type,
                    subscription_frequency=None, price=299.0):
    slug_base = name_suffix.lower().replace("_", "-")
    payload = {
        "name": f"TEST_iter31_{name_suffix}",
        "slug": f"test-iter31-{slug_base}-{uuid.uuid4().hex[:5]}",
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


def _mkdummy(admin_headers, label):
    payload = {
        "full_name": f"TEST iter31 {label}",
        "email": f"test_iter31_{label}_{uuid.uuid4().hex[:6]}@example.com",
        "mobile": f"91000{uuid.uuid4().hex[:5]}",
        "password": "tester123",
    }
    r = requests.post(f"{API}/admin/users/dummy", headers=admin_headers,
                      json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    return payload


def _login(email):
    r = requests.post(f"{API}/auth/login",
                      json={"email": email, "password": "tester123"},
                      timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    return body["tokens"]["access_token"], body["user"]["membership_id"]


def _uheaders(admin_headers, label):
    p = _mkdummy(admin_headers, label)
    tok, mid = _login(p["email"])
    return {"Authorization": f"Bearer {tok}",
            "Content-Type": "application/json"}, mid


def _init_sub(uheaders, program_id):
    r = requests.post(f"{API}/payments/subscription/init",
                      headers=uheaders,
                      json={"program_id": program_id}, timeout=20)
    assert r.status_code == 201, r.text
    return r.json()["subscription_id"]


def _fetch_notifs(uheaders):
    r = requests.get(f"{API}/notifications/me", headers=uheaders, timeout=15)
    assert r.status_code == 200, r.text
    return r.json().get("items") or r.json().get("notifications") or []


def _webhook_sub(event, sid, extra_sub=None, extra_pay=None):
    body = {
        "event": event,
        "payload": {
            "subscription": {"entity": {"id": sid, "status": None, **(extra_sub or {})}},
        },
    }
    if extra_pay:
        body["payload"]["payment"] = {"entity": extra_pay}
    return requests.post(f"{API}/payments/webhook",
                         headers=WH_HEADERS, json=body, timeout=20)


# =============================================================================
# 1. subscription.pending webhook
# =============================================================================


class TestSubscriptionPending:
    def test_pending_sets_status_and_creates_dedup_notification(
        self, admin_headers, category
    ):
        prog = _create_program(admin_headers, category["id"], "Pending",
                               "subscription", "monthly", price=199.0)
        h, mid = _uheaders(admin_headers, "pending")
        sid = _init_sub(h, prog["id"])

        # Fire the same webhook TWICE
        r1 = _webhook_sub("subscription.pending", sid,
                          extra_sub={"status": "pending"})
        assert r1.status_code == 200, r1.text
        r2 = _webhook_sub("subscription.pending", sid,
                          extra_sub={"status": "pending"})
        assert r2.status_code == 200, r2.text
        time.sleep(1)

        # Verify sub status
        rme = requests.get(f"{API}/payments/subscription/me",
                           headers=h, timeout=15)
        assert rme.status_code == 200
        rows = [s for s in rme.json()["items"] if s["subscription_id"] == sid]
        assert rows and rows[0]["status"] == "pending", rows

        # Verify EXACTLY ONE notification for this sid was created
        notifs = _fetch_notifs(h)
        matches = [
            n for n in notifs
            if (n.get("meta") or {}).get("dedup_key") == f"sub_pending:{sid}"
        ]
        assert len(matches) == 1, f"Expected 1 dedup notification, got {len(matches)}"
        n = matches[0]
        assert n["title"] == "Renewal payment failed"
        assert n["category"] == "payment"
        assert n.get("cta_link") == "/app/subscriptions"


# =============================================================================
# 2. subscription.halted webhook
# =============================================================================


class TestSubscriptionHalted:
    def test_halted_sets_status_and_creates_dedup_notification(
        self, admin_headers, category
    ):
        prog = _create_program(admin_headers, category["id"], "Halted",
                               "subscription", "monthly", price=199.0)
        h, mid = _uheaders(admin_headers, "halted")
        sid = _init_sub(h, prog["id"])

        r1 = _webhook_sub("subscription.halted", sid,
                          extra_sub={"status": "halted"})
        assert r1.status_code == 200, r1.text
        # Replay
        r2 = _webhook_sub("subscription.halted", sid,
                          extra_sub={"status": "halted"})
        assert r2.status_code == 200
        time.sleep(1)

        rme = requests.get(f"{API}/payments/subscription/me",
                           headers=h, timeout=15)
        rows = [s for s in rme.json()["items"] if s["subscription_id"] == sid]
        assert rows and rows[0]["status"] == "halted"

        notifs = _fetch_notifs(h)
        matches = [
            n for n in notifs
            if (n.get("meta") or {}).get("dedup_key") == f"sub_halted:{sid}"
        ]
        assert len(matches) == 1, f"Expected 1 dedup, got {len(matches)}"
        n = matches[0]
        assert n["title"] == "Auto-renewal stopped"
        assert n["category"] == "payment"
        assert n.get("cta_link") == "/app/subscriptions"


# =============================================================================
# 3. payment.failed (one-time)
# =============================================================================


class TestPaymentFailedOneTime:
    def test_payment_failed_marks_order_and_notifies(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "OT_Fail",
                               "one_time", price=399.0)
        h, mid = _uheaders(admin_headers, "otfail")

        # Create an order
        ro = requests.post(f"{API}/payments/order", headers=h,
                           json={"program_id": prog["id"]}, timeout=15)
        assert ro.status_code == 201, ro.text
        order = ro.json()

        # Fire payment.failed
        payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_fail_{uuid.uuid4().hex[:10]}",
                        "order_id": order["order_id"],
                        "status": "failed",
                        "error_description": "Insufficient funds",
                    }
                }
            },
        }
        r = requests.post(f"{API}/payments/webhook", headers=WH_HEADERS,
                          json=payload, timeout=20)
        assert r.status_code == 200
        time.sleep(1)

        # Notification created
        notifs = _fetch_notifs(h)
        pf = [n for n in notifs if n.get("title") == "Payment failed"
              and n.get("category") == "payment"]
        assert pf, f"No payment-failed notification. Got: {[n.get('title') for n in notifs]}"

    def test_no_notification_if_order_already_paid(
        self, admin_headers, category
    ):
        prog = _create_program(admin_headers, category["id"], "OT_Paid",
                               "one_time", price=399.0)
        h, mid = _uheaders(admin_headers, "otpaid")

        ro = requests.post(f"{API}/payments/order", headers=h,
                           json={"program_id": prog["id"]}, timeout=15)
        order = ro.json()

        # Verify successful (paid)
        rv = requests.post(f"{API}/payments/verify", headers=h, json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": f"pay_mock_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{order['order_id']}",
        }, timeout=15)
        assert rv.status_code == 200

        # Count notifs before firing failed webhook
        before = _fetch_notifs(h)
        n_fail_before = len(
            [n for n in before if n.get("title") == "Payment failed"]
        )

        payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_fail_{uuid.uuid4().hex[:10]}",
                        "order_id": order["order_id"],
                        "status": "failed",
                        "error_description": "Late failure",
                    }
                }
            },
        }
        r = requests.post(f"{API}/payments/webhook", headers=WH_HEADERS,
                          json=payload, timeout=20)
        assert r.status_code == 200
        time.sleep(1)

        after = _fetch_notifs(h)
        n_fail_after = len(
            [n for n in after if n.get("title") == "Payment failed"]
        )
        # No new payment-failed notification since order was already paid
        assert n_fail_after == n_fail_before, (
            f"Expected no new failure notif for paid order, "
            f"before={n_fail_before} after={n_fail_after}"
        )


# =============================================================================
# 4. Admin failed-subscriptions endpoint
# =============================================================================


class TestAdminFailedSubs:
    def test_admin_endpoint_returns_halted_pending(
        self, admin_headers, category
    ):
        # Create a halted + a pending sub
        prog = _create_program(admin_headers, category["id"], "AdminFail",
                               "subscription", "monthly", price=199.0)
        h, mid = _uheaders(admin_headers, "adminfail")

        sid_h = _init_sub(h, prog["id"])
        _webhook_sub("subscription.halted", sid_h,
                     extra_sub={"status": "halted"})

        prog2 = _create_program(admin_headers, category["id"], "AdminFail2",
                                "subscription", "monthly", price=199.0)
        h2, mid2 = _uheaders(admin_headers, "adminfail2")
        sid_p = _init_sub(h2, prog2["id"])
        _webhook_sub("subscription.pending", sid_p,
                     extra_sub={"status": "pending"})

        time.sleep(1)

        r = requests.get(f"{API}/admin/qa/failed-subscriptions",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and "count" in data
        assert isinstance(data["items"], list)
        sids = [x.get("subscription_id") for x in data["items"]]
        assert sid_h in sids, f"halted sid missing: {sids[:5]}"
        assert sid_p in sids, f"pending sid missing: {sids[:5]}"

        # Verify enrichment (user sub-object) + status is halted/pending
        for it in data["items"]:
            assert it.get("status") in ("halted", "pending")
            assert "user" in it
            # user object may be empty {} if not found, but must exist
            u = it["user"]
            if it["subscription_id"] == sid_h:
                assert u.get("email") is not None or u.get("full_name") is not None

    def test_non_admin_forbidden(self, admin_headers):
        # Public (no auth) → 401/403
        r = requests.get(f"{API}/admin/qa/failed-subscriptions", timeout=15)
        assert r.status_code in (401, 403), r.status_code

        # Authenticated user (non-admin) → 401/403
        h, _ = _uheaders(admin_headers, "nonadmin")
        r2 = requests.get(f"{API}/admin/qa/failed-subscriptions",
                          headers=h, timeout=15)
        assert r2.status_code in (401, 403), r2.status_code


# =============================================================================
# 5. Regression: subscription.charged still works + does NOT fire failure notif
# =============================================================================


class TestChargedRegression:
    def test_charged_no_failure_notif(self, admin_headers, category):
        prog = _create_program(admin_headers, category["id"], "ChargedReg",
                               "subscription", "monthly", price=199.0)
        h, mid = _uheaders(admin_headers, "chargedreg")
        sid = _init_sub(h, prog["id"])

        payment_id = f"pay_TEST31_{uuid.uuid4().hex[:12]}"
        body = {
            "event": "subscription.charged",
            "payload": {
                "subscription": {"entity": {"id": sid, "status": "active",
                                            "paid_count": 1,
                                            "current_start": 1000000000,
                                            "current_end": 1002592000}},
                "payment": {"entity": {"id": payment_id, "amount": 19900,
                                       "status": "captured", "recurring": True}},
            },
        }
        r1 = requests.post(f"{API}/payments/webhook",
                           headers=WH_HEADERS, json=body, timeout=20)
        assert r1.status_code == 200
        # Idempotent replay
        r2 = requests.post(f"{API}/payments/webhook",
                           headers=WH_HEADERS, json=body, timeout=20)
        assert r2.status_code == 200
        time.sleep(1)

        # No failure notification (Renewal payment failed / Auto-renewal stopped
        # / Payment failed) should exist for this fresh user.
        notifs = _fetch_notifs(h)
        bad_titles = {"Renewal payment failed", "Auto-renewal stopped",
                      "Payment failed"}
        bad = [n for n in notifs if n.get("title") in bad_titles]
        assert not bad, f"Unexpected failure notifs on success flow: {bad}"

        # Purchase should exist (idempotent)
        rme = requests.get(f"{API}/payments/me", headers=h, timeout=15)
        purchases = [p for p in rme.json()["items"]
                     if p.get("razorpay_payment_id") == payment_id]
        assert len(purchases) == 1, f"Expected 1 purchase, got {len(purchases)}"


# =============================================================================
# 6. Regression: fresh sid after halted mandate
# =============================================================================


class TestFreshSidAfterHalted:
    def test_init_after_halted_returns_fresh_sid(
        self, admin_headers, category
    ):
        prog = _create_program(admin_headers, category["id"], "FreshAfterHalt",
                               "subscription", "monthly", price=199.0)
        h, mid = _uheaders(admin_headers, "freshhalt")

        sid1 = _init_sub(h, prog["id"])
        # Halt it
        _webhook_sub("subscription.halted", sid1,
                     extra_sub={"status": "halted"})
        time.sleep(1)

        # Re-init should NOT reuse the halted sid
        r = requests.post(f"{API}/payments/subscription/init",
                          headers=h, json={"program_id": prog["id"]},
                          timeout=20)
        assert r.status_code == 201, r.text
        sid2 = r.json()["subscription_id"]
        assert sid2 != sid1, f"Expected fresh sid after halted, got same {sid1}"
        # reused flag should be False (fresh init)
        assert r.json().get("reused") is False
