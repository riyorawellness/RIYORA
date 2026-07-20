"""Iter33 — Dynamic Razorpay plan cache + webhook-independent subscription verify.

Covers:
  1. POST /payments/subscription/init returns 201 with plan_id (starts with
     'plan_' in live mode or 'mock_plan_' in mock mode), subscription_id,
     short_url, key_id, breakdown.
  2. Plan-cache reuse: two /init calls for the same (program, freq, amount)
     result in ONE subscription_plans_cache row (one Razorpay plan.create).
  3. Mock-mode webhook-independent verify: first /verify materialises a
     program_purchases row with status='active'; second /verify is
     idempotent (same purchase_id).
  4. Idempotency: after verify materialises the purchase, a subscription.charged
     webhook with a DIFFERENT razorpay_payment_id for the same
     (subscription_id, cycle) does NOT create a duplicate purchase row
     (dedup by subscription_id + subscription_cycle).
  5. Regression: /payments/subscription/me returns 200. /cancel works.
     Free-program enrol + one-time payment (order + verify) untouched.

The tests flip RAZORPAY_MOCK_MODE=true during the test session and restore
it at the end.
"""
from __future__ import annotations

import os
import uuid
import time
import hmac
import hashlib
import json
import pathlib
import subprocess

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fall back to reading /app/frontend/.env directly
    for line in pathlib.Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"

TESTER_EMAIL = "qa-tester@example.com"
TESTER_PASSWORD = "tester123"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def _mock_mode_on():
    """Enable RAZORPAY_MOCK_MODE for the whole session and restart backend."""
    env_path = pathlib.Path("/app/backend/.env")
    original = env_path.read_text()
    new = []
    saw = False
    for line in original.splitlines():
        if line.startswith("RAZORPAY_MOCK_MODE"):
            new.append("RAZORPAY_MOCK_MODE=true")
            saw = True
        else:
            new.append(line)
    if not saw:
        new.append("RAZORPAY_MOCK_MODE=true")
    env_path.write_text("\n".join(new) + "\n")
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=False)
    # Wait for backend to come up
    for _ in range(30):
        try:
            r = requests.get(f"{API}/health", timeout=2)
            if r.status_code < 500:
                break
        except Exception:
            pass
        time.sleep(1)
    yield
    # Restore
    env_path.write_text(original)
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=False)
    for _ in range(30):
        try:
            r = requests.get(f"{API}/health", timeout=2)
            if r.status_code < 500:
                break
        except Exception:
            pass
        time.sleep(1)


@pytest.fixture(scope="session")
def admin_token(_mock_mode_on):
    r = requests.post(f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="session")
def tester_token(_mock_mode_on):
    # Email fallback login
    r = requests.post(f"{API}/auth/login", json={"email": TESTER_EMAIL, "password": TESTER_PASSWORD}, timeout=15)
    if r.status_code != 200:
        # Might need mobile login instead
        r = requests.post(f"{API}/auth/login", json={"mobile": TESTER_EMAIL, "password": TESTER_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="session")
def sub_program(admin_token):
    """Create a fresh subscription program (monthly)."""
    admin_hdr = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    # Create category
    slug = f"iter33-{uuid.uuid4().hex[:6]}"
    cat = requests.post(f"{API}/categories/admin", headers=admin_hdr, json={
        "name": f"TEST_iter33_{slug}", "slug": slug, "order_index": 999,
    }, timeout=15)
    assert cat.status_code in (200, 201), cat.text
    cat_id = cat.json()["id"]

    p = requests.post(f"{API}/programs/admin", headers=admin_hdr, json={
        "name": f"TEST_iter33_MonthlySub_{slug}",
        "slug": f"iter33-mon-{slug}",
        "price": 199,
        "discount": 0,
        "validity_days": 30,
        "category_id": cat_id,
        "payment_type": "subscription",
        "subscription_frequency": "monthly",
        "is_active": True,
    }, timeout=15)
    assert p.status_code in (200, 201), p.text
    return p.json()


@pytest.fixture(scope="session")
def onetime_program(admin_token):
    admin_hdr = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    slug = f"iter33ot-{uuid.uuid4().hex[:6]}"
    cat = requests.post(f"{API}/categories/admin", headers=admin_hdr, json={
        "name": f"TEST_iter33ot_{slug}", "slug": slug, "order_index": 999,
    }, timeout=15)
    assert cat.status_code in (200, 201), cat.text
    p = requests.post(f"{API}/programs/admin", headers=admin_hdr, json={
        "name": f"TEST_iter33_OneTime_{slug}",
        "slug": f"iter33-ot-{slug}",
        "price": 299,
        "discount": 0,
        "validity_days": 365,
        "category_id": cat.json()["id"],
        "payment_type": "one_time",
        "is_active": True,
    }, timeout=15)
    assert p.status_code in (200, 201), p.text
    return p.json()


@pytest.fixture(scope="session")
def free_program(admin_token):
    admin_hdr = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    slug = f"iter33fr-{uuid.uuid4().hex[:6]}"
    cat = requests.post(f"{API}/categories/admin", headers=admin_hdr, json={
        "name": f"TEST_iter33fr_{slug}", "slug": slug, "order_index": 999,
    }, timeout=15)
    p = requests.post(f"{API}/programs/admin", headers=admin_hdr, json={
        "name": f"TEST_iter33_Free_{slug}",
        "slug": f"iter33-fr-{slug}",
        "price": 0,
        "discount": 0,
        "validity_days": 30,
        "category_id": cat.json()["id"],
        "payment_type": "free",
        "is_active": True,
    }, timeout=15)
    assert p.status_code in (200, 201), p.text
    return p.json()


def _mongo():
    import pymongo
    return pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _cleanup_active_purchases(membership_id: str, program_id: str):
    """Make sure the tester doesn't already have an active purchase for this program."""
    db = _mongo()
    db.program_purchases.delete_many({"user_membership_id": membership_id, "program_id": program_id})
    db.subscriptions.delete_many({"user_membership_id": membership_id, "program_id": program_id})


def _tester_membership_id(tester_token: str) -> str:
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tester_token}"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["membership_id"]


# ============================================================================
# Tests
# ============================================================================

class TestSubscriptionInitAndPlanCache:
    """Iter33 (1) + (2): /init returns plan+sub ids and caches plan by (program,freq,amount)."""

    def test_init_creates_subscription_with_plan_id(self, tester_token, sub_program):
        mid = _tester_membership_id(tester_token)
        _cleanup_active_purchases(mid, sub_program["id"])
        db = _mongo()
        # Also clear the plan cache row so we test first-time creation
        db.subscription_plans_cache.delete_many({"program_id": sub_program["id"]})

        r = requests.post(
            f"{API}/payments/subscription/init",
            headers={"Authorization": f"Bearer {tester_token}"},
            json={"program_id": sub_program["id"]},
            timeout=30,
        )
        assert r.status_code == 201, f"{r.status_code} {r.text}"
        data = r.json()
        # Structural asserts
        assert "subscription_id" in data and isinstance(data["subscription_id"], str)
        assert "plan_id" in data and isinstance(data["plan_id"], str)
        # In mock mode plan_id starts with 'mock_plan_'; in live mode it starts with 'plan_'
        assert data["plan_id"].startswith("plan_") or data["plan_id"].startswith("mock_plan_"), \
            f"unexpected plan_id: {data['plan_id']}"
        assert data.get("short_url"), "short_url should be present"
        assert data.get("key_id"), "key_id should be present"
        assert data.get("breakdown"), "breakdown should be present"
        assert data["breakdown"].get("total") is not None
        # In mock mode the SID should start with mock_sub_
        assert data["subscription_id"].startswith("mock_sub_") or data["subscription_id"].startswith("sub_"), \
            f"unexpected subscription_id: {data['subscription_id']}"

    def test_plan_cache_reuse_on_second_init(self, tester_token, sub_program):
        """Two /init calls for the same (program, freq, amount) should reuse the
        same cached plan_id AND result in ONE row in subscription_plans_cache."""
        mid = _tester_membership_id(tester_token)
        db = _mongo()
        # Clean state
        _cleanup_active_purchases(mid, sub_program["id"])
        db.subscription_plans_cache.delete_many({"program_id": sub_program["id"]})

        # First call
        r1 = requests.post(
            f"{API}/payments/subscription/init",
            headers={"Authorization": f"Bearer {tester_token}"},
            json={"program_id": sub_program["id"]},
            timeout=30,
        )
        assert r1.status_code == 201, r1.text
        plan_id_1 = r1.json()["plan_id"]
        sid_1 = r1.json()["subscription_id"]

        # Second call — will reuse the subscription row (reused=True) but the
        # important assertion is on the plan cache
        r2 = requests.post(
            f"{API}/payments/subscription/init",
            headers={"Authorization": f"Bearer {tester_token}"},
            json={"program_id": sub_program["id"]},
            timeout=30,
        )
        assert r2.status_code == 201, r2.text
        plan_id_2 = r2.json()["plan_id"]

        assert plan_id_1 == plan_id_2, "plan_id must be reused"

        # Now also clean up the sub row and re-init to force a fresh subscription
        # (but plan cache must still be reused).
        db.subscriptions.delete_many({"subscription_id": sid_1})
        r3 = requests.post(
            f"{API}/payments/subscription/init",
            headers={"Authorization": f"Bearer {tester_token}"},
            json={"program_id": sub_program["id"]},
            timeout=30,
        )
        assert r3.status_code == 201, r3.text
        assert r3.json()["plan_id"] == plan_id_1, "plan_id must still be cached"

        # Only one row in the cache for this program.
        rows = list(db.subscription_plans_cache.find({"program_id": sub_program["id"], "deleted_at": None}))
        assert len(rows) == 1, f"expected 1 cached plan row, got {len(rows)}: {rows}"
        assert rows[0]["plan_id"] == plan_id_1


class TestWebhookIndependentVerify:
    """Iter33 (3) + (4): mock-mode /verify materialises purchase; webhook is idempotent."""

    def test_verify_materialises_purchase_and_is_idempotent(self, tester_token, sub_program):
        mid = _tester_membership_id(tester_token)
        _cleanup_active_purchases(mid, sub_program["id"])
        db = _mongo()
        db.subscription_plans_cache.delete_many({"program_id": sub_program["id"]})

        # Fresh subscription
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers={"Authorization": f"Bearer {tester_token}"},
            json={"program_id": sub_program["id"]},
            timeout=30,
        )
        assert r.status_code == 201, r.text
        sid = r.json()["subscription_id"]

        # First verify → materialises purchase
        v1 = requests.post(
            f"{API}/payments/subscription/{sid}/verify",
            headers={"Authorization": f"Bearer {tester_token}"},
            timeout=30,
        )
        assert v1.status_code == 200, v1.text
        d1 = v1.json()
        assert d1["status"] == "active", f"expected status=active, got {d1['status']}"
        assert d1.get("purchase_id"), "purchase_id must be returned"
        purchase_id_1 = d1["purchase_id"]

        # Verify one row exists
        rows = list(db.program_purchases.find({"subscription_id": sid, "deleted_at": None}))
        assert len(rows) == 1, f"expected 1 purchase row, got {len(rows)}"
        assert rows[0]["id"] == purchase_id_1

        # Second verify → idempotent
        v2 = requests.post(
            f"{API}/payments/subscription/{sid}/verify",
            headers={"Authorization": f"Bearer {tester_token}"},
            timeout=30,
        )
        assert v2.status_code == 200, v2.text
        assert v2.json()["purchase_id"] == purchase_id_1

        rows2 = list(db.program_purchases.find({"subscription_id": sid, "deleted_at": None}))
        assert len(rows2) == 1, f"expected still 1 purchase row after second verify, got {len(rows2)}"

    def test_webhook_after_verify_is_deduped_by_cycle(self, tester_token, sub_program):
        """After verify has materialised the purchase (with a placeholder payment_id),
        a subscription.charged webhook with a DIFFERENT razorpay_payment_id for the
        same (subscription_id, cycle) must NOT create a duplicate purchase row."""
        mid = _tester_membership_id(tester_token)
        _cleanup_active_purchases(mid, sub_program["id"])
        db = _mongo()
        db.subscription_plans_cache.delete_many({"program_id": sub_program["id"]})

        # Init + verify (mock mode → verify materialises immediately)
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers={"Authorization": f"Bearer {tester_token}"},
            json={"program_id": sub_program["id"]},
            timeout=30,
        )
        sid = r.json()["subscription_id"]
        v = requests.post(
            f"{API}/payments/subscription/{sid}/verify",
            headers={"Authorization": f"Bearer {tester_token}"},
            timeout=30,
        )
        assert v.status_code == 200
        purchase_id_1 = v.json()["purchase_id"]

        # Simulate subscription.charged webhook with a DIFFERENT payment id
        # In mock mode `verify_webhook_signature` returns True for any signature
        # that startswith "mock_". So we can craft one directly.
        payload = {
            "event": "subscription.charged",
            "payload": {
                "subscription": {
                    "entity": {
                        "id": sid,
                        "status": "active",
                        "paid_count": 1,
                        "current_start": 1,
                        "current_end": 2,
                    }
                },
                "payment": {
                    "entity": {
                        "id": f"pay_webhook_{uuid.uuid4().hex[:12]}",
                        "amount": 19900,
                        "status": "captured",
                        "method": "upi",
                    }
                },
            },
        }
        body = json.dumps(payload).encode()

        r_wh = requests.post(
            f"{API}/payments/webhook",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": "mock_signature_iter33",
            },
            timeout=15,
        )
        assert r_wh.status_code in (200, 204), f"webhook returned {r_wh.status_code} {r_wh.text}"

        # Assert still exactly ONE purchase row for this subscription
        rows = list(db.program_purchases.find({"subscription_id": sid, "deleted_at": None}))
        assert len(rows) == 1, (
            f"Expected 1 purchase row after webhook, got {len(rows)}: "
            f"{[r.get('razorpay_payment_id') for r in rows]}"
        )
        # And it's still the same purchase_id
        assert rows[0]["id"] == purchase_id_1


class TestRegression:
    """Iter33 (5): regressions must still pass."""

    def test_subscription_me_returns_list(self, tester_token):
        r = requests.get(
            f"{API}/payments/subscription/me",
            headers={"Authorization": f"Bearer {tester_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_subscription_cancel_works(self, tester_token, admin_token):
        """Cancel a fresh subscription in mock mode."""
        # Create a NEW subscription for a different program to avoid interference
        mid = _tester_membership_id(tester_token)
        admin_hdr = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        slug = f"iter33c-{uuid.uuid4().hex[:6]}"
        cat = requests.post(f"{API}/categories/admin", headers=admin_hdr, json={
            "name": f"TEST_iter33c_{slug}", "slug": slug, "order_index": 999,
        }, timeout=15).json()
        p = requests.post(f"{API}/programs/admin", headers=admin_hdr, json={
            "name": f"TEST_iter33_Cancel_{slug}",
            "slug": f"iter33-cn-{slug}",
            "price": 149, "discount": 0, "validity_days": 30, "category_id": cat["id"],
            "payment_type": "subscription", "subscription_frequency": "monthly",
            "is_active": True,
        }, timeout=15).json()
        _cleanup_active_purchases(mid, p["id"])
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers={"Authorization": f"Bearer {tester_token}"},
            json={"program_id": p["id"]},
            timeout=30,
        )
        assert r.status_code == 201
        sid = r.json()["subscription_id"]
        cnc = requests.post(
            f"{API}/payments/subscription/{sid}/cancel",
            headers={"Authorization": f"Bearer {tester_token}"},
            timeout=15,
        )
        assert cnc.status_code == 200, cnc.text
        assert cnc.json()["status"] in ("cancelled", "created", "pending")

    def test_free_program_enrol(self, tester_token, free_program):
        mid = _tester_membership_id(tester_token)
        # Clean prior enrolment
        _mongo().program_enrolments.delete_many({
            "user_membership_id": mid, "program_id": free_program["id"]
        })
        r = requests.post(
            f"{API}/programs/{free_program['id']}/enrol-free",
            headers={"Authorization": f"Bearer {tester_token}"},
            timeout=15,
        )
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "active"

    def test_one_time_order_and_verify(self, tester_token, onetime_program):
        mid = _tester_membership_id(tester_token)
        _cleanup_active_purchases(mid, onetime_program["id"])
        r = requests.post(
            f"{API}/payments/order",
            headers={"Authorization": f"Bearer {tester_token}"},
            json={"program_id": onetime_program["id"]},
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text
        d = r.json()
        assert "order_id" in d
        assert d.get("amount_paise", 0) > 0
        # Verify with mock signature
        v = requests.post(
            f"{API}/payments/verify",
            headers={"Authorization": f"Bearer {tester_token}"},
            json={
                "razorpay_order_id": d["order_id"],
                "razorpay_payment_id": f"pay_mock_{uuid.uuid4().hex[:12]}",
                "razorpay_signature": f"mock_sig_{d['order_id']}",
            },
            timeout=15,
        )
        assert v.status_code in (200, 201), v.text


class TestFrontendCardRemoved:
    """Iter33 (6): confirm admin payment settings JSX no longer references plan IDs."""

    def test_admin_payment_settings_source_has_no_plan_ids_card(self):
        src = pathlib.Path("/app/frontend/src/pages/AdminPaymentSettings.jsx").read_text()
        assert "rzp-plan-ids-card" not in src
        assert "razorpay_plan_id" not in src
        assert "Subscription plan IDs" not in src
        assert "Subscription Plans" not in src


class TestPlanCacheIndex:
    """Iter33 (context): the review request claimed a mongo unique index
    `uniq_program_freq_amount_live` on `subscription_plans_cache` was added.
    This test verifies whether that index actually exists — if not, it's a
    real bug because two concurrent /init calls could race on plan creation.
    """

    def test_subscription_plans_cache_has_unique_index(self):
        db = _mongo()
        # touch the collection so it exists (safe: no docs are written)
        _ = list(db.subscription_plans_cache.find().limit(1))
        info = db.subscription_plans_cache.index_information()
        # Look for any unique index over (program_id, frequency, amount_paise)
        has_unique_triple = False
        for name, spec in info.items():
            keys = [k[0] for k in spec.get("key", [])]
            if spec.get("unique") and set(keys) >= {"program_id", "frequency", "amount_paise"}:
                has_unique_triple = True
                break
        assert has_unique_triple, (
            f"Missing unique index on subscription_plans_cache over "
            f"(program_id, frequency, amount_paise). Existing indexes: {info}"
        )
