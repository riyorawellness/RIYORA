"""Iter26 RETEST — verifies the E11000/subscription_id unique-index fix.

Adds NEW regression tests on top of test_iter26_payment_type_and_subscriptions.py:
  1. Two different dummy users can each subscribe to two different subscription
     programs → 4 inits succeed (no E11000 duplicate-key collision).
  2. Plan caching: two DIFFERENT users initing on the SAME subscription program
     receive the SAME plan_id (server reuses cached _razorpay_plans mapping).
  3. Second cancel returns 409.
  4. Legacy shadowing cancel route in payments.py is gone; new subscription_id
     lookup works.
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://rw-subscription-hub.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PWD = "Admin@12345"


# ------------------------------------------------------------------ helpers --

@pytest.fixture(scope="module")
def admin_headers() -> dict:
    r = requests.post(f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PWD}, timeout=15)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def category_id(admin_headers) -> str:
    r = requests.post(
        f"{API}/categories/admin",
        headers=admin_headers,
        json={"name": "TEST Retest Cat", "slug": f"testrcat-{uuid.uuid4().hex[:6]}", "order_index": 999},
        timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _make_program(admin_headers, category_id, name_suffix: str, freq: str = "monthly", price: int = 499) -> str:
    r = requests.post(
        f"{API}/programs/admin",
        headers=admin_headers,
        json={
            "name": f"TEST Sub Program {name_suffix}",
            "slug": f"testrp-{uuid.uuid4().hex[:6]}",
            "price": price,
            "validity_days": 30,
            "category_id": category_id,
            "gst_percent": 0,
            "payment_type": "subscription",
            "subscription_frequency": freq,
        },
        timeout=15,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _make_dummy(admin_headers, email: str, name: str = "QA Retester", password: str = "tester123") -> str:
    """Create dummy user via admin API. Returns the tester's access_token."""
    r = requests.post(
        f"{API}/admin/users/dummy",
        headers=admin_headers,
        json={"full_name": name, "email": email, "password": password},
        timeout=15,
    )
    assert r.status_code in (200, 201, 409), r.text
    log = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert log.status_code == 200, log.text
    return log.json()["tokens"]["access_token"]


_created_programs: list[str] = []
_created_subs: list[tuple[str, str]] = []  # (token, sub_id)


@pytest.fixture(scope="module", autouse=True)
def _cleanup(admin_headers):
    yield
    # Best-effort cancel for any live subs left over
    for token, sid in _created_subs:
        try:
            requests.post(
                f"{API}/payments/subscription/{sid}/cancel",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
        except Exception:
            pass
    for pid in _created_programs:
        try:
            requests.delete(f"{API}/programs/admin/{pid}", headers=admin_headers, timeout=10)
        except Exception:
            pass


# ==================================================================== TESTS ==

class TestUniqueIndexRegression:
    """Two different users × two different programs = 4 inits, no E11000."""

    def test_four_inits_across_two_users_two_programs(self, admin_headers, category_id):
        # Two subscription programs
        prog_a = _make_program(admin_headers, category_id, "A")
        prog_b = _make_program(admin_headers, category_id, "B")
        _created_programs.extend([prog_a, prog_b])

        # Two dummy users
        email_1 = f"qa-retest-{uuid.uuid4().hex[:6]}@example.com"
        email_2 = f"qa-retest-{uuid.uuid4().hex[:6]}@example.com"
        token_1 = _make_dummy(admin_headers, email_1, name="Retest User 1")
        token_2 = _make_dummy(admin_headers, email_2, name="Retest User 2")

        # 4 inits — no E11000 = the sparse+unique fix works.
        collected: list[dict] = []
        for tok, pid, tag in (
            (token_1, prog_a, "u1×A"),
            (token_1, prog_b, "u1×B"),
            (token_2, prog_a, "u2×A"),
            (token_2, prog_b, "u2×B"),
        ):
            r = requests.post(
                f"{API}/payments/subscription/init",
                headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                json={"program_id": pid},
                timeout=30,
            )
            if r.status_code == 502:
                pytest.skip(f"[{tag}] Live Razorpay unavailable: {r.text}")
            assert r.status_code == 201, f"[{tag}] {r.status_code} {r.text}"
            payload = r.json()
            assert "subscription_id" in payload
            assert payload["subscription_id"].startswith("sub_"), payload
            collected.append({"tag": tag, "tok": tok, "pid": pid, **payload})
            _created_subs.append((tok, payload["subscription_id"]))

        # All 4 subscription_ids unique.
        sub_ids = [c["subscription_id"] for c in collected]
        assert len(set(sub_ids)) == 4, f"Duplicate subscription ids: {sub_ids}"

        # Plan caching: (u1×A) and (u2×A) → same plan_id. Same for prog_b.
        plans_by_prog: dict[str, set[str]] = {prog_a: set(), prog_b: set()}
        for c in collected:
            plans_by_prog[c["pid"]].add(c["plan_id"])
        assert len(plans_by_prog[prog_a]) == 1, f"prog_a plan_id not cached: {plans_by_prog[prog_a]}"
        assert len(plans_by_prog[prog_b]) == 1, f"prog_b plan_id not cached: {plans_by_prog[prog_b]}"

        # Save to class for downstream tests
        TestUniqueIndexRegression._collected = collected


class TestCancelFlow:
    """Second cancel → 409 (uses subscription_id-based lookup)."""

    def test_double_cancel_returns_409(self):
        collected = getattr(TestUniqueIndexRegression, "_collected", None)
        if not collected:
            pytest.skip("No subs created in prior test")

        # Pick the first one.
        c = collected[0]
        headers = {"Authorization": f"Bearer {c['tok']}", "Content-Type": "application/json"}
        r = requests.post(f"{API}/payments/subscription/{c['subscription_id']}/cancel", headers=headers, timeout=20)
        if r.status_code == 502:
            # Razorpay refuses to cancel unauthenticated mandate. Skip
            # (this is a Razorpay live-mode limitation, not a code bug).
            pytest.skip(f"Live Razorpay cancel refused: {r.text}")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"

        r2 = requests.post(f"{API}/payments/subscription/{c['subscription_id']}/cancel", headers=headers, timeout=20)
        assert r2.status_code == 409, r2.text


class TestSameUserSameProgramDup:
    """Same user + same program while active must still 409 (business rule)."""

    def test_same_user_second_init_409(self, admin_headers):
        collected = getattr(TestUniqueIndexRegression, "_collected", None)
        if not collected:
            pytest.skip("no subs")
        c = collected[1] if len(collected) > 1 else collected[0]  # u1×B
        headers = {"Authorization": f"Bearer {c['tok']}", "Content-Type": "application/json"}
        r = requests.post(
            f"{API}/payments/subscription/init",
            headers=headers,
            json={"program_id": c["pid"]},
            timeout=20,
        )
        assert r.status_code == 409, r.text
        assert "already have an active subscription" in r.json().get("detail", "").lower()
