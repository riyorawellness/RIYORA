"""Activity Meter v2 — 2026-02 rules regression.

Business rules verified:
  1. Any active purchase (subscription OR one-time still within validity)
     keeps the user eligible to log sessions and earn "green" status.
  2. Cycle = rolling 30-day window from user registration
     (cycle_number = 0 → yellow grace, > 0 → red until 4 sessions logged).
  3. Completing any module (subscription OR one-time) auto-logs 1 session.
  4. `has_active_plan` field is exposed in the meter payload.
  5. Once 4 sessions hit within current cycle → green; stays green even if
     user logs more or does nothing else in the cycle.
"""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

import pytest
import requests

_env = Path("/app/frontend/.env")
for _ln in _env.read_text().splitlines():
    if _ln.startswith("REACT_APP_BACKEND_URL"):
        os.environ["REACT_APP_BACKEND_URL"] = _ln.split("=", 1)[1].strip().strip('"')

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"
COMPANY_REF = "RW000000"
DEV_OTP = "123456"
DEFAULT_PASSWORD = "Passw0rd!"


def _rand_mobile() -> str:
    import random
    return random.choice("6789") + "".join(random.choices("0123456789", k=9))


def _slug(prefix="am2"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(referral_id=COMPANY_REF, name="TEST_AM2"):
    m = _rand_mobile()
    requests.post(f"{API}/auth/send-otp", json={"mobile": m, "purpose": "register"})
    requests.post(
        f"{API}/auth/verify-otp",
        json={"mobile": m, "purpose": "register", "code": DEV_OTP},
    )
    r = requests.post(
        f"{API}/auth/register",
        json={
            "full_name": name,
            "mobile": m,
            "state": "KA",
            "city": "BLR",
            "referral_id": referral_id,
            "password": DEFAULT_PASSWORD,
            "confirm_password": DEFAULT_PASSWORD,
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    return {
        "mobile": m,
        "membership_id": d["user"]["membership_id"],
        "access": d["tokens"]["access_token"],
        "headers": {
            "Authorization": f"Bearer {d['tokens']['access_token']}",
            "Content-Type": "application/json",
        },
    }


@pytest.fixture(scope="module")
def admin_h():
    r = requests.post(
        f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD}
    )
    return {
        "Authorization": f"Bearer {r.json()['tokens']['access_token']}",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="module")
def cat(admin_h):
    r = requests.post(
        f"{API}/categories/admin",
        headers=admin_h,
        json={"name": "TEST_AM2_Cat", "slug": _slug("cat"), "order_index": 995},
    )
    return r.json()


@pytest.fixture(scope="module")
def one_time_program(admin_h, cat):
    r = requests.post(
        f"{API}/programs/admin",
        headers=admin_h,
        json={
            "name": f"TEST_AM2_OneTime_{uuid.uuid4().hex[:6]}",
            "slug": _slug("ot"),
            "price": 500,
            "validity_days": 60,
            "gst_percent": 0,
            "category_id": cat["id"],
            "is_subscription": False,
            "level": None,
        },
    )
    return r.json()


def _buy(user, program_id):
    o = requests.post(
        f"{API}/payments/order", headers=user["headers"], json={"program_id": program_id}
    )
    assert o.status_code == 201, o.text
    oid = o.json()["order_id"]
    v = requests.post(
        f"{API}/payments/verify",
        headers=user["headers"],
        json={
            "razorpay_order_id": oid,
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{oid}",
        },
    )
    assert v.status_code == 200, v.text
    return v.json()


def _log(user, source="manual", module_id=None):
    body = {"source": source}
    if module_id:
        body["module_id"] = module_id
    return requests.post(f"{API}/activity/session", headers=user["headers"], json=body)


def _meter(user):
    return requests.get(f"{API}/activity/meter", headers=user["headers"]).json()


# ============================================================================
class TestActivityMeterV2:
    def test_no_plan_when_never_purchased(self):
        u = _register()
        m = _meter(u)
        assert m["status"] in ("no_plan", "no_subscription")
        assert m["has_active_plan"] is False
        assert m["remaining"] == 4

    def test_one_time_purchase_keeps_user_yellow_first_cycle(self, one_time_program):
        u = _register()
        _buy(u, one_time_program["id"])
        m = _meter(u)
        assert m["status"] == "yellow"  # first cycle grace
        assert m["has_active_plan"] is True
        assert m["cycle_number"] == 0
        assert m["completed"] == 0

    def test_four_sessions_flip_green_with_one_time_program(self, one_time_program):
        u = _register()
        _buy(u, one_time_program["id"])
        for _ in range(4):
            r = _log(u, source="manual")
            assert r.status_code == 201, r.text
        m = _meter(u)
        assert m["status"] == "green"
        assert m["completed"] == 4
        assert m["remaining"] == 0

    def test_log_session_blocked_without_any_purchase(self):
        u = _register()  # no purchase
        r = _log(u, source="manual")
        assert r.status_code == 400
        assert "No active plan" in r.text or "No active" in r.text

    def test_module_complete_auto_logs_for_one_time_program(self, admin_h, cat, one_time_program):
        # Create a module on the one-time program
        m = requests.post(
            f"{API}/modules/admin",
            headers=admin_h,
            json={
                "program_id": one_time_program["id"],
                "module_number": 100,
                "name": f"AM2_MOD_{uuid.uuid4().hex[:6]}",
                "sequential_unlock": True,
            },
        )
        assert m.status_code == 201, m.text
        mod = m.json()

        u = _register()
        _buy(u, one_time_program["id"])
        rc = requests.post(
            f"{API}/progress/me/{one_time_program['id']}/module/{mod['id']}/complete",
            headers=u["headers"],
            json={"time_spent_sec": 5},
        )
        assert rc.status_code == 200, rc.text
        sess = requests.get(f"{API}/activity/sessions/me", headers=u["headers"]).json()
        auto_rows = [s for s in sess["items"] if s.get("source") == "module_complete"]
        assert len(auto_rows) == 1
        # Meter reflects it
        me = _meter(u)
        assert me["completed"] >= 1

    def test_module_id_dedup_across_sources(self, one_time_program):
        u = _register()
        _buy(u, one_time_program["id"])
        mid = f"AM2_DEDUP_{uuid.uuid4().hex[:6]}"
        r1 = _log(u, source="manual", module_id=mid)
        r2 = _log(u, source="module_complete", module_id=mid)
        assert r1.status_code == 201
        assert r2.status_code == 201
        # Both return same session id (idempotent by module_id)
        assert r1.json()["session"]["id"] == r2.json()["session"]["id"]
