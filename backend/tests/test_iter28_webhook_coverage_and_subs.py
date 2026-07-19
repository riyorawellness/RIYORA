"""
iter28: Regression + new-feature tests for
  1) NEW  GET  /api/admin/qa/live-check/webhook-coverage  (admin only, 9-event checklist)
  2) REG  GET  /api/payments/subscription/me              (user-scoped list)
  3) REG  POST /api/payments/subscription/{sid}/cancel    (smart cancel — reachability only)

Base URL is taken from REACT_APP_BACKEND_URL. No default value.
"""
from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": "9999999999", "password": "Admin@12345"},
        timeout=30,
    )
    assert r.status_code == 200, f"admin/login failed: {r.status_code} {r.text}"
    tok = r.json()["tokens"]["access_token"]
    assert isinstance(tok, str) and len(tok) > 0
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def dummy_user_token():
    """Login as pre-seeded dummy user via email/password path."""
    r = requests.post(
        f"{API}/auth/login",
        json={"email": "qa-tester@example.com", "password": "tester123"},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"dummy user login unavailable: {r.status_code} {r.text[:200]}")
    body = r.json()
    tok = body.get("tokens", {}).get("access_token") or body.get("access_token")
    assert tok, f"no access_token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def user_headers(dummy_user_token):
    return {"Authorization": f"Bearer {dummy_user_token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# 1) NEW: webhook-coverage endpoint
# ---------------------------------------------------------------------------
class TestWebhookCoverage:
    """/admin/qa/live-check/webhook-coverage — admin-only 9-event checklist."""

    REQUIRED_ONE_TIME = {"payment.captured", "order.paid", "payment.failed"}
    REQUIRED_SUBSCRIPTION = {
        "subscription.authenticated",
        "subscription.charged",
        "subscription.completed",
        "subscription.cancelled",
        "subscription.halted",
        "subscription.pending",
    }
    REQUIRED_ALL = REQUIRED_ONE_TIME | REQUIRED_SUBSCRIPTION

    def test_unauth_401_or_403(self):
        r = requests.get(f"{API}/admin/qa/live-check/webhook-coverage", timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_non_admin_forbidden(self, user_headers):
        r = requests.get(
            f"{API}/admin/qa/live-check/webhook-coverage",
            headers=user_headers,
            timeout=30,
        )
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code} {r.text[:200]}"

    def test_admin_returns_checklist(self, admin_headers):
        r = requests.get(
            f"{API}/admin/qa/live-check/webhook-coverage?lookback_days=30",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"admin call failed: {r.status_code} {r.text[:200]}"
        data = r.json()

        # Top-level shape
        for key in ("lookback_days", "required_events", "checklist",
                    "extra_events_seen", "webhook_paths"):
            assert key in data, f"missing key {key} in response: {list(data.keys())}"

        assert data["lookback_days"] == 30
        assert isinstance(data["required_events"], list)
        assert isinstance(data["checklist"], list)

        # 9 required events total
        assert set(data["required_events"]) == self.REQUIRED_ALL
        assert len(data["checklist"]) == 9

        # Each checklist item shape
        seen_events = set()
        by_cat = {"one_time": 0, "subscription": 0}
        for item in data["checklist"]:
            for k in ("event", "seen", "last_seen_at", "category"):
                assert k in item, f"checklist item missing {k}: {item}"
            assert isinstance(item["seen"], bool)
            assert item["category"] in ("one_time", "subscription")
            by_cat[item["category"]] += 1
            seen_events.add(item["event"])
            # When seen=False, last_seen_at must be None
            if not item["seen"]:
                assert item["last_seen_at"] is None

        # Category counts: 3 one_time + 6 subscription
        assert by_cat["one_time"] == 3
        assert by_cat["subscription"] == 6
        assert seen_events == self.REQUIRED_ALL

        # Webhook paths hint
        assert "/api/payments/razorpay/webhook" in data["webhook_paths"]
        assert "/api/payments/webhook" in data["webhook_paths"]

    def test_lookback_days_clamping(self, admin_headers):
        # 0 is falsy → the endpoint falls back to default 30
        r = requests.get(
            f"{API}/admin/qa/live-check/webhook-coverage?lookback_days=0",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["lookback_days"] == 30

        # 9999 → clamped to 365
        r2 = requests.get(
            f"{API}/admin/qa/live-check/webhook-coverage?lookback_days=9999",
            headers=admin_headers,
            timeout=30,
        )
        assert r2.status_code == 200
        assert r2.json()["lookback_days"] == 365

        # 7 → passes through
        r3 = requests.get(
            f"{API}/admin/qa/live-check/webhook-coverage?lookback_days=7",
            headers=admin_headers,
            timeout=30,
        )
        assert r3.status_code == 200
        assert r3.json()["lookback_days"] == 7


# ---------------------------------------------------------------------------
# 2) REGRESSION: GET /api/payments/subscription/me
# ---------------------------------------------------------------------------
class TestSubscriptionMe:
    def test_unauth_401(self):
        r = requests.get(f"{API}/payments/subscription/me", timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_returns_items_and_total(self, user_headers):
        r = requests.get(
            f"{API}/payments/subscription/me",
            headers=user_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"subscription/me failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert "items" in data, f"missing items: {data}"
        assert "total" in data, f"missing total: {data}"
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert data["total"] == len(data["items"])


# ---------------------------------------------------------------------------
# 3) REGRESSION: POST /api/payments/subscription/{sid}/cancel — reachability
# ---------------------------------------------------------------------------
class TestSubscriptionCancelReachable:
    def test_unauth(self):
        r = requests.post(
            f"{API}/payments/subscription/does_not_exist/cancel",
            timeout=30,
        )
        assert r.status_code in (401, 403)

    def test_unknown_sid_returns_404(self, user_headers):
        r = requests.post(
            f"{API}/payments/subscription/sub_TEST_iter28_missing/cancel",
            headers=user_headers,
            timeout=30,
        )
        # Route must exist (not 405/404 route-not-found). Business logic returns 404 for unknown sub.
        assert r.status_code in (404, 400), (
            f"unexpected status for unknown sid: {r.status_code} {r.text[:200]}"
        )
