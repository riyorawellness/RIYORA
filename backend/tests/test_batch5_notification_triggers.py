"""Batch 5 — Notification triggers audit.

Verifies the 7 auto-triggers required by the pre-launch checklist:
  1. Payment Success (Razorpay)
  2. Payment Failed (Razorpay signature invalid)
  3. Payment Success (Manual QR approve) — already covered by phase 11 tests
  4. Payment Failed (Manual QR reject)   — already covered by phase 11 tests
  5. New Module Unlocked
  6. Referral Income
  7. New Program (broadcast)
  8. Validity Expiring (via /admin/notifications/scan-expiring)
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
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


def _rand_mobile():
    import random
    return random.choice("6789") + "".join(random.choices("0123456789", k=9))


def _slug(prefix="b5"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(referral_id=COMPANY_REF, name="TEST_B5"):
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
        json={"name": "TEST_B5_Cat", "slug": _slug("cat"), "order_index": 980},
    )
    return r.json()


def _list_notifs(headers):
    return requests.get(
        f"{API}/notifications/me?page=1&page_size=50", headers=headers
    ).json()


def _titles(headers):
    return [n["title"] for n in _list_notifs(headers).get("items", [])]


class TestNotificationTriggers:
    def test_payment_success_razorpay(self, admin_h, cat):
        prog = requests.post(
            f"{API}/programs/admin",
            headers=admin_h,
            json={
                "name": f"TEST_B5_SUCC_{uuid.uuid4().hex[:6]}",
                "slug": _slug("succ"),
                "price": 300,
                "validity_days": 30,
                "gst_percent": 0,
                "category_id": cat["id"],
                "is_subscription": False,
                "payment_mode": "razorpay",
            },
        ).json()
        u = _register()
        o = requests.post(
            f"{API}/payments/order",
            headers=u["headers"],
            json={"program_id": prog["id"]},
        ).json()
        v = requests.post(
            f"{API}/payments/verify",
            headers=u["headers"],
            json={
                "razorpay_order_id": o["order_id"],
                "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:10]}",
                "razorpay_signature": f"mock_sig_{o['order_id']}",
            },
        )
        assert v.status_code == 200
        titles = _titles(u["headers"])
        assert any("Payment successful" in t for t in titles), titles

    def test_payment_failed_razorpay_bad_signature(self, admin_h, cat):
        prog = requests.post(
            f"{API}/programs/admin",
            headers=admin_h,
            json={
                "name": f"TEST_B5_FAIL_{uuid.uuid4().hex[:6]}",
                "slug": _slug("fail"),
                "price": 300,
                "validity_days": 30,
                "gst_percent": 0,
                "category_id": cat["id"],
                "is_subscription": False,
                "payment_mode": "razorpay",
            },
        ).json()
        u = _register()
        o = requests.post(
            f"{API}/payments/order",
            headers=u["headers"],
            json={"program_id": prog["id"]},
        ).json()
        # Wrong signature — must NOT start with "mock_sig_"
        v = requests.post(
            f"{API}/payments/verify",
            headers=u["headers"],
            json={
                "razorpay_order_id": o["order_id"],
                "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:10]}",
                "razorpay_signature": "totally_wrong",
            },
        )
        assert v.status_code == 400
        titles = _titles(u["headers"])
        assert any("Payment failed" in t for t in titles), titles

    def test_referral_income_notifies_sponsor(self, admin_h, cat):
        sponsor = _register(name="TEST_B5_Sponsor")

        # Make sponsor eligible for commission: needs an active plan + 4 sessions.
        sponsor_prog = requests.post(
            f"{API}/programs/admin",
            headers=admin_h,
            json={
                "name": f"TEST_B5_SPONSOR_PLAN_{uuid.uuid4().hex[:6]}",
                "slug": _slug("splan"),
                "price": 100,
                "validity_days": 90,
                "gst_percent": 0,
                "category_id": cat["id"],
                "is_subscription": False,
                "payment_mode": "razorpay",
            },
        ).json()
        so = requests.post(
            f"{API}/payments/order",
            headers=sponsor["headers"],
            json={"program_id": sponsor_prog["id"]},
        ).json()
        requests.post(
            f"{API}/payments/verify",
            headers=sponsor["headers"],
            json={
                "razorpay_order_id": so["order_id"],
                "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:10]}",
                "razorpay_signature": f"mock_sig_{so['order_id']}",
            },
        )
        # Log 4 activity sessions to hit "green".
        for i in range(4):
            requests.post(
                f"{API}/activity/session",
                headers=sponsor["headers"],
                json={"source": "manual", "notes": f"seed-{i}"},
            )
        meter = requests.get(
            f"{API}/activity/meter", headers=sponsor["headers"]
        ).json()
        assert meter["status"] == "green", meter

        buyer = _register(referral_id=sponsor["membership_id"], name="TEST_B5_Buyer")
        prog = requests.post(
            f"{API}/programs/admin",
            headers=admin_h,
            json={
                "name": f"TEST_B5_REF_{uuid.uuid4().hex[:6]}",
                "slug": _slug("ref"),
                "price": 1000,
                "validity_days": 30,
                "gst_percent": 0,
                "category_id": cat["id"],
                "is_subscription": False,
                "payment_mode": "razorpay",
            },
        ).json()
        o = requests.post(
            f"{API}/payments/order",
            headers=buyer["headers"],
            json={"program_id": prog["id"]},
        ).json()
        requests.post(
            f"{API}/payments/verify",
            headers=buyer["headers"],
            json={
                "razorpay_order_id": o["order_id"],
                "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:10]}",
                "razorpay_signature": f"mock_sig_{o['order_id']}",
            },
        )
        titles = _titles(sponsor["headers"])
        assert any("referral income" in t for t in titles), titles

    def test_new_module_unlocked(self, admin_h, cat):
        prog = requests.post(
            f"{API}/programs/admin",
            headers=admin_h,
            json={
                "name": f"TEST_B5_MOD_{uuid.uuid4().hex[:6]}",
                "slug": _slug("mod"),
                "price": 200,
                "validity_days": 30,
                "gst_percent": 0,
                "category_id": cat["id"],
                "is_subscription": False,
                "payment_mode": "razorpay",
            },
        ).json()
        # 3 modules
        for i in (1, 2, 3):
            requests.post(
                f"{API}/modules/admin",
                headers=admin_h,
                json={
                    "program_id": prog["id"],
                    "module_number": i,
                    "name": f"M{i}",
                    "sequential_unlock": True,
                },
            )
        u = _register()
        # Grant access via order+verify
        o = requests.post(
            f"{API}/payments/order",
            headers=u["headers"],
            json={"program_id": prog["id"]},
        ).json()
        requests.post(
            f"{API}/payments/verify",
            headers=u["headers"],
            json={
                "razorpay_order_id": o["order_id"],
                "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:10]}",
                "razorpay_signature": f"mock_sig_{o['order_id']}",
            },
        )
        # List modules for user, get id of M1, mark complete
        mods = requests.get(
            f"{API}/modules/me/by-program/{prog['id']}", headers=u["headers"]
        ).json()
        m1 = next(m for m in mods["modules"] if m["module_number"] == 1)
        rc = requests.post(
            f"{API}/progress/me/{prog['id']}/module/{m1['id']}/complete",
            headers=u["headers"],
            json={"time_spent_sec": 10},
        )
        assert rc.status_code == 200
        titles = _titles(u["headers"])
        assert any("New module unlocked" in t for t in titles), titles

    def test_new_program_broadcast(self, admin_h, cat):
        subscriber = _register(name="TEST_B5_Subscriber")
        pre_titles = set(_titles(subscriber["headers"]))
        # Admin creates new active program → broadcast to all users
        name = f"TEST_B5_NEWPROG_{uuid.uuid4().hex[:6]}"
        requests.post(
            f"{API}/programs/admin",
            headers=admin_h,
            json={
                "name": name,
                "slug": _slug("newprog"),
                "price": 500,
                "validity_days": 30,
                "gst_percent": 0,
                "category_id": cat["id"],
                "is_subscription": False,
                "is_active": True,
                "payment_mode": "razorpay",
            },
        )
        # Subscriber's broadcast should now include the "New program available"
        titles = _titles(subscriber["headers"])
        assert any("New program available" in t for t in titles), (pre_titles, titles)

    def test_validity_expiring_scan(self, admin_h, cat):
        # Create a purchase that expires in EXACTLY 3 days.
        prog = requests.post(
            f"{API}/programs/admin",
            headers=admin_h,
            json={
                "name": f"TEST_B5_EXP_{uuid.uuid4().hex[:6]}",
                "slug": _slug("exp"),
                "price": 200,
                "validity_days": 3,  # short validity
                "gst_percent": 0,
                "category_id": cat["id"],
                "is_subscription": False,
                "payment_mode": "razorpay",
            },
        ).json()
        u = _register()
        o = requests.post(
            f"{API}/payments/order",
            headers=u["headers"],
            json={"program_id": prog["id"]},
        ).json()
        requests.post(
            f"{API}/payments/verify",
            headers=u["headers"],
            json={
                "razorpay_order_id": o["order_id"],
                "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:10]}",
                "razorpay_signature": f"mock_sig_{o['order_id']}",
            },
        )
        # Fire the scan
        scan = requests.post(
            f"{API}/notifications/admin/scan-expiring", headers=admin_h
        )
        assert scan.status_code == 200, scan.text
        notifs = _list_notifs(u["headers"]).get("items", [])
        expiring = next(
            (n for n in notifs if "expires in" in (n.get("title") or "").lower()),
            None,
        )
        assert expiring, notifs
        # Renew CTA must deep-link to /app/pay/{program_id}
        assert expiring.get("cta_link") == f"/app/pay/{prog['id']}"
        assert expiring.get("cta_label") == "Renew"

    def test_scan_expiring_idempotent(self, admin_h):
        # Run scan twice — same user should not receive duplicates due to dedup_key
        r1 = requests.post(
            f"{API}/notifications/admin/scan-expiring", headers=admin_h
        ).json()
        r2 = requests.post(
            f"{API}/notifications/admin/scan-expiring", headers=admin_h
        ).json()
        assert r2["notifications_created"] == 0, (r1, r2)
