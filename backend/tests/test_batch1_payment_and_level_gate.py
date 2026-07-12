"""Batch 1 — Per-program payment mode + Level-gate visibility regression."""
import uuid
import os
from pathlib import Path

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


def _slug(prefix="b1"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(referral_id=COMPANY_REF, name="TEST_B1"):
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
        json={"name": "TEST_B1_Cat", "slug": _slug("cat"), "order_index": 990},
    )
    return r.json()


def _make_program(admin_h, cat_id, **overrides):
    body = {
        "name": f"TEST_B1_{uuid.uuid4().hex[:6]}",
        "slug": _slug("p"),
        "price": 500,
        "validity_days": 30,
        "gst_percent": 18,
        "category_id": cat_id,
        "is_subscription": False,
        **overrides,
    }
    r = requests.post(f"{API}/programs/admin", headers=admin_h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ========== Per-program payment mode ========================================
class TestPerProgramPaymentMode:
    def test_default_falls_back_to_global(self, admin_h, cat):
        prog = _make_program(admin_h, cat["id"])
        u = _register()
        # No override → global "manual_qr" (default seed)
        r = requests.get(
            f"{API}/payments/mode",
            headers=u["headers"],
            params={"program_id": prog["id"]},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["payment_mode"] in ("manual_qr", "razorpay", "both")
        assert d.get("program_override") is False

    def test_per_program_override(self, admin_h, cat):
        prog = _make_program(admin_h, cat["id"], payment_mode="razorpay")
        u = _register()
        r = requests.get(
            f"{API}/payments/mode",
            headers=u["headers"],
            params={"program_id": prog["id"]},
        )
        d = r.json()
        assert d["payment_mode"] == "razorpay"
        assert d["program_override"] is True

    def test_razorpay_only_blocks_manual_submit(self, admin_h, cat):
        prog = _make_program(admin_h, cat["id"], payment_mode="razorpay")
        u = _register()
        r = requests.post(
            f"{API}/payments/manual/submit",
            headers=u["headers"],
            json={
                "program_id": prog["id"],
                "utr": "TEST123",
                "transaction_date": "2026-02-01",
                "screenshot_url": "/uploads/screenshot/x.png",
            },
        )
        assert r.status_code == 409
        assert "razorpay" in r.text.lower()

    def test_manual_qr_only_blocks_razorpay_order(self, admin_h, cat):
        prog = _make_program(admin_h, cat["id"], payment_mode="manual_qr")
        u = _register()
        r = requests.post(
            f"{API}/payments/order",
            headers=u["headers"],
            json={"program_id": prog["id"]},
        )
        assert r.status_code == 409
        assert "qr" in r.text.lower()

    def test_admin_can_update_payment_mode(self, admin_h, cat):
        prog = _make_program(admin_h, cat["id"])
        assert prog.get("payment_mode") is None
        r = requests.put(
            f"{API}/programs/admin/{prog['id']}",
            headers=admin_h,
            json={"payment_mode": "both"},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("payment_mode") == "both"


# ========== Level-gate visibility ===========================================
class TestLevelGate:
    def test_status_returns_eligibility_block(self, admin_h, cat):
        prog = _make_program(admin_h, cat["id"], level=1)
        u = _register()
        r = requests.get(f"{API}/programs/{prog['id']}/status", headers=u["headers"])
        assert r.status_code == 200
        d = r.json()
        assert "eligibility" in d
        # Level 1 has no prereq → eligible=True
        assert d["eligibility"]["eligible"] is True

    def test_level_2_locked_without_level_1_completion(self, admin_h, cat):
        _l1 = _make_program(admin_h, cat["id"], level=1, name=f"L1_{uuid.uuid4().hex[:4]}", slug=_slug("l1"))
        l2 = _make_program(admin_h, cat["id"], level=2, name=f"L2_{uuid.uuid4().hex[:4]}", slug=_slug("l2"))
        u = _register()
        r = requests.get(f"{API}/programs/{l2['id']}/status", headers=u["headers"])
        assert r.status_code == 200
        d = r.json()
        assert d["eligibility"]["eligible"] is False
        assert d["eligibility"]["reason"]
        assert "complete" in d["eligibility"]["reason"].lower()

    def test_subscription_bypasses_level_gate(self, admin_h, cat):
        sub = _make_program(admin_h, cat["id"], level=3, is_subscription=True)
        u = _register()
        r = requests.get(f"{API}/programs/{sub['id']}/status", headers=u["headers"])
        d = r.json()
        assert d["eligibility"]["eligible"] is True
