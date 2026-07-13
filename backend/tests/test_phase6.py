"""RIYORA WELLNESS — Phase 6 Backend Regression Suite (Refer & Earn Engine).

Covers:
  * Activity Meter lifecycle: no_subscription → yellow → green → red (expired)
  * Session idempotency (module_id) + manual increment
  * Auto-log on module complete (subscription only)
  * Referrals: dashboard, QR share, team by level (1/2/3)
  * Commission engine: happy path, ineligibility, 3-level chain, RW000000 skip, idempotency
  * Global commission settings override
  * Admin commissions: list + filters + approve/reject/bulk-approve + summary
  * Payouts: pending-by-user, create, mark-paid, cancel + validations
  * User payouts
  * Reports: 5 PDFs + 400 for unknown
  * Referral settings roundtrip
  * Auth guards (401 no token, 403 user token on admin routes)

Mock signature contract: mock_sig_<order_id> (Phase 5).
"""
import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tests.helpers.firebase_seed import seed_test_user  # noqa: E402

import pytest
import requests

# ---- Load public URL from frontend/.env ------------------------------------
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
    return random.choice("6789") + "".join(random.choices("0123456789", k=9))


def _slug(prefix: str = "p6") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(referral_id: str = COMPANY_REF, name: str = "TEST_P6User"):
    """Seed a dummy user + return a login-shaped dict (post-Firebase migration)."""
    r = seed_test_user(full_name=name, sponsor=referral_id)
    return {
        "mobile": r["mobile"],
        "membership_id": r["membership_id"],
        "password": r["password"],
        "token": r["access_token"],
        "refresh_token": r["refresh_token"],
        "headers": {
            "Authorization": f"Bearer {r['access_token']}",
            "Content-Type": "application/json",
        },
    }


def _admin_headers():
    r = requests.post(
        f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {
        "Authorization": f"Bearer {r.json()['tokens']['access_token']}",
        "Content-Type": "application/json",
    }


def _create_category(admin_h):
    r = requests.post(
        f"{API}/categories/admin",
        headers=admin_h,
        json={"name": "TEST_P6_Cat", "slug": _slug("cat"), "order_index": 996},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_program(
    admin_h,
    cat_id,
    price=1000,
    discount=0,
    gst_percent=18,
    validity_days=30,
    is_subscription=False,
    level=None,
    commission_override=None,
    name_prefix="P6",
):
    body = {
        "name": f"TEST_{name_prefix}_{uuid.uuid4().hex[:6]}",
        "slug": _slug(name_prefix.lower()),
        "price": price,
        "discount": discount,
        "gst_percent": gst_percent,
        "validity_days": validity_days,
        "category_id": cat_id,
        "is_subscription": is_subscription,
        # Force Razorpay path — most phase6 tests exercise `/payments/order`.
        # This overrides the global (manual_qr) default per Batch 1 change.
        "payment_mode": "razorpay",
    }
    if level is not None:
        body["level"] = level
    if commission_override is not None:
        body["commission_override"] = commission_override
    r = requests.post(f"{API}/programs/admin", headers=admin_h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _subscribe(user, program_id, plan="monthly"):
    r = requests.post(
        f"{API}/payments/subscription",
        headers=user["headers"],
        json={"program_id": program_id, "plan": plan},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _log_session(user, module_id=None, source="manual", notes=None):
    body = {"source": source}
    if module_id:
        body["module_id"] = module_id
    if notes:
        body["notes"] = notes
    r = requests.post(f"{API}/activity/session", headers=user["headers"], json=body)
    return r


def _make_active_green(user, sub_program_id, sessions=4):
    """Subscribe user and log required sessions to reach green status."""
    _subscribe(user, sub_program_id)
    for _ in range(sessions):
        r = _log_session(user, source="manual")
        assert r.status_code == 201, r.text
    # Verify green
    m = requests.get(f"{API}/activity/meter", headers=user["headers"]).json()
    assert m["status"] == "green", m
    return m


def _buy_program(user, program_id):
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
    return v.json(), oid


# ============ Fixtures ======================================================
@pytest.fixture(scope="module")
def admin_h():
    return _admin_headers()


@pytest.fixture(scope="module")
def cat(admin_h):
    return _create_category(admin_h)


@pytest.fixture(scope="module")
def sub_program(admin_h, cat):
    """A subscription program (Inner Peace-like)."""
    return _create_program(
        admin_h, cat["id"], price=999, validity_days=30, is_subscription=True,
        name_prefix="IP"
    )


@pytest.fixture(scope="module")
def buy_program(admin_h, cat):
    """A non-subscription paid program used for commission purchases.
    Uses level=None so sequence-gate does not apply."""
    return _create_program(
        admin_h, cat["id"], price=1000, discount=0, gst_percent=18,
        validity_days=30, is_subscription=False, level=None, name_prefix="BUY"
    )


# ============ 1. ACTIVITY METER lifecycle ==================================
class TestActivityMeter:
    def test_no_subscription_status(self):
        u = _register()
        r = requests.get(f"{API}/activity/meter", headers=u["headers"])
        assert r.status_code == 200
        m = r.json()
        # New rule (2026-02): status is "no_plan" when user has no active purchase.
        # Old alias "no_subscription" is kept in the Literal for backward compat.
        assert m["status"] in ("no_plan", "no_subscription")
        assert m["completed"] == 0
        assert m["required"] == 4
        assert m["remaining"] == 4

    def test_yellow_after_subscribe(self, sub_program):
        u = _register()
        _subscribe(u, sub_program["id"])
        m = requests.get(f"{API}/activity/meter", headers=u["headers"]).json()
        assert m["status"] == "yellow"
        assert m["completed"] == 0
        assert m["remaining"] == 4
        assert m.get("cycle_start") and m.get("cycle_end")
        assert m.get("days_left") is not None and m["days_left"] >= 0

    def test_green_after_4_sessions(self, sub_program):
        u = _register()
        _subscribe(u, sub_program["id"])
        for _ in range(4):
            r = _log_session(u, source="manual")
            assert r.status_code == 201
        m = requests.get(f"{API}/activity/meter", headers=u["headers"]).json()
        assert m["status"] == "green"
        assert m["completed"] >= 4
        assert m["remaining"] == 0


# ============ 2. Session idempotency & manual increment ====================
class TestSessionIdempotency:
    def test_module_id_dedup_same_cycle(self, sub_program):
        u = _register()
        _subscribe(u, sub_program["id"])
        mid = f"TEST_mod_{uuid.uuid4().hex[:8]}"
        r1 = _log_session(u, module_id=mid).json()
        r2 = _log_session(u, module_id=mid).json()
        # Same session id returned; not double counted
        assert r1["session"]["id"] == r2["session"]["id"]
        # Count in cycle == 1
        sess = requests.get(f"{API}/activity/sessions/me", headers=u["headers"]).json()
        mod_rows = [s for s in sess["items"] if s.get("module_id") == mid]
        assert len(mod_rows) == 1

    def test_manual_without_module_id_each_increments(self, sub_program):
        u = _register()
        _subscribe(u, sub_program["id"])
        for _ in range(3):
            r = _log_session(u, source="manual")
            assert r.status_code == 201
        m = requests.get(f"{API}/activity/meter", headers=u["headers"]).json()
        assert m["completed"] == 3
        # 4th → green
        _log_session(u, source="manual")
        m2 = requests.get(f"{API}/activity/meter", headers=u["headers"]).json()
        assert m2["completed"] == 4 and m2["status"] == "green"


# ============ 3. Auto-log on module complete ================================
class TestAutoLogModule:
    def test_module_complete_on_sub_program_creates_session(self, admin_h, cat):
        # Create a fresh subscription program + module (so auto-log fires)
        prog = _create_program(
            admin_h, cat["id"], price=999, validity_days=30,
            is_subscription=True, name_prefix="AUTOSUB",
        )
        m = requests.post(
            f"{API}/modules/admin",
            headers=admin_h,
            json={
                "program_id": prog["id"],
                "module_number": 1,
                "name": "AUTOSUB_M1",
                "sequential_unlock": True,
            },
        )
        assert m.status_code == 201, m.text
        mod = m.json()

        u = _register()
        _subscribe(u, prog["id"])
        # Complete module → should auto-log an activity session
        rc = requests.post(
            f"{API}/progress/me/{prog['id']}/module/{mod['id']}/complete",
            headers=u["headers"],
            json={"time_spent_sec": 5},
        )
        assert rc.status_code == 200, rc.text
        sess = requests.get(f"{API}/activity/sessions/me", headers=u["headers"]).json()
        auto_rows = [s for s in sess["items"] if s.get("source") == "module_complete"]
        assert len(auto_rows) >= 1

    def test_non_subscription_module_complete_now_logs_session(self, admin_h, cat):
        """New rule (2026-02): completing a module of ANY purchased program
        (subscription OR one-time still within validity) auto-logs an
        activity session. Previously only subscription programs did."""
        prog = _create_program(
            admin_h, cat["id"], price=100, validity_days=30,
            is_subscription=False, level=None, name_prefix="NONSUBMOD",
        )
        m = requests.post(
            f"{API}/modules/admin",
            headers=admin_h,
            json={
                "program_id": prog["id"],
                "module_number": 1,
                "name": "NONSUBMOD_M1",
                "sequential_unlock": True,
            },
        )
        assert m.status_code == 201, m.text
        mod = m.json()

        u = _register()
        _buy_program(u, prog["id"])
        rc = requests.post(
            f"{API}/progress/me/{prog['id']}/module/{mod['id']}/complete",
            headers=u["headers"],
            json={"time_spent_sec": 3},
        )
        assert rc.status_code == 200, rc.text
        sess = requests.get(f"{API}/activity/sessions/me", headers=u["headers"]).json()
        # NEW rule: one-time program purchase also counts towards activity.
        auto_rows = [s for s in sess["items"] if s.get("source") == "module_complete"]
        assert len(auto_rows) >= 1


# ============ 4. Referrals dashboard + team + QR ============================
class TestReferralsDashboard:
    def test_dashboard_shape(self):
        u = _register()
        r = requests.get(
            f"{API}/referrals/dashboard",
            headers=u["headers"],
            params={"app_url": "https://example.com"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        for k in (
            "membership_id",
            "referral_id",
            "referral_link",
            "earnings",
            "activity",
            "team_counts",
            "total_downline",
        ):
            assert k in d, f"missing key {k}"
        assert d["referral_link"].endswith(f"/join/{u['membership_id']}")
        assert set(d["team_counts"].keys()) == {"L1", "L2", "L3"}

    def test_team_counts_match_actual(self):
        s = _register()
        # 2 direct
        d1 = _register(referral_id=s["membership_id"])
        _d2 = _register(referral_id=s["membership_id"])
        # 1 L2
        _l2 = _register(referral_id=d1["membership_id"])

        d = requests.get(f"{API}/referrals/dashboard", headers=s["headers"]).json()
        assert d["team_counts"]["L1"] == 2
        assert d["team_counts"]["L2"] == 1
        assert d["team_counts"]["L3"] == 0
        assert d["total_downline"] == 3

    def test_qr_dataurl(self):
        u = _register()
        r = requests.get(
            f"{API}/referrals/share/qr",
            headers=u["headers"],
            params={"app_url": "https://example.com"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["data_url"].startswith("data:image/png;base64,")
        b64 = d["data_url"].split(",", 1)[1]
        assert len(b64) > 500
        assert d["link"].endswith(f"/join/{u['membership_id']}")

    def test_team_by_level(self):
        s = _register()
        d1 = _register(referral_id=s["membership_id"])
        _d2 = _register(referral_id=s["membership_id"])
        l2 = _register(referral_id=d1["membership_id"])
        _l3 = _register(referral_id=l2["membership_id"])

        r1 = requests.get(
            f"{API}/referrals/team", headers=s["headers"], params={"level": 1}
        ).json()
        assert r1["count"] == 2
        for it in r1["items"]:
            assert "membership_id" in it
            assert "full_name" in it
            assert "joining_date" in it
            assert "activity_status" in it
            assert "has_subscription" in it

        r2 = requests.get(
            f"{API}/referrals/team", headers=s["headers"], params={"level": 2}
        ).json()
        assert r2["count"] == 1

        r3 = requests.get(
            f"{API}/referrals/team", headers=s["headers"], params={"level": 3}
        ).json()
        assert r3["count"] == 1


# ============ 5. Commission engine ==========================================
class TestCommissionEngine:
    def test_happy_path_L1(self, admin_h, sub_program, buy_program):
        # Sponsor S green
        s = _register(name="TEST_SponsorL1")
        _make_active_green(s, sub_program["id"], sessions=4)
        # Buyer B referred by S
        b = _register(referral_id=s["membership_id"], name="TEST_BuyerB")
        # Purchase ₹1000 + 18% = ₹1180
        v, _ = _buy_program(b, buy_program["id"])

        # Sponsor's commissions
        rows = requests.get(
            f"{API}/commissions/me",
            headers=s["headers"],
            params={"page_size": 100},
        ).json()
        matching = [r for r in rows["items"] if r["purchase_id"] == v["purchase_id"]]
        assert len(matching) == 1
        row = matching[0]
        assert row["level"] == 1
        assert row["amount"] == 118.0
        assert row["status"] == "pending"
        assert row["buyer_membership_id"] == b["membership_id"]

    def test_ineligible_sponsor_rejected(self, buy_program):
        s2 = _register(name="TEST_SponsorInelig")
        # S2 has NO subscription → no_subscription status
        b2 = _register(referral_id=s2["membership_id"], name="TEST_BuyerB2")
        v, _ = _buy_program(b2, buy_program["id"])

        rows = requests.get(
            f"{API}/commissions/me",
            headers=s2["headers"],
            params={"page_size": 100},
        ).json()
        matching = [r for r in rows["items"] if r["purchase_id"] == v["purchase_id"]]
        assert len(matching) == 1
        row = matching[0]
        assert row["status"] == "rejected"
        assert row.get("reason") and "not active" in row["reason"].lower()

    def test_3_level_chain(self, admin_h, sub_program, buy_program):  # noqa
        _admin_h = admin_h
        A = _register(name="TEST_A")
        _make_active_green(A, sub_program["id"])
        B = _register(referral_id=A["membership_id"], name="TEST_B")
        _make_active_green(B, sub_program["id"])
        C = _register(referral_id=B["membership_id"], name="TEST_C")
        _make_active_green(C, sub_program["id"])
        D = _register(referral_id=C["membership_id"], name="TEST_D")
        v, _ = _buy_program(D, buy_program["id"])

        # Admin view — pull all 3 rows for this purchase
        admin_rows = requests.get(
            f"{API}/commissions/admin",
            headers=_admin_h,
            params={"page_size": 200, "q": D["membership_id"]},
        )
        assert admin_rows.status_code == 200
        purchase_rows = [
            r for r in admin_rows.json()["items"] if r["purchase_id"] == v["purchase_id"]
        ]
        assert len(purchase_rows) == 3, purchase_rows
        by_sponsor = {r["sponsor_membership_id"]: r for r in purchase_rows}
        assert C["membership_id"] in by_sponsor
        assert B["membership_id"] in by_sponsor
        assert A["membership_id"] in by_sponsor
        # RW000000 not in the ledger
        assert COMPANY_REF not in by_sponsor

        assert by_sponsor[C["membership_id"]]["level"] == 1
        assert by_sponsor[C["membership_id"]]["amount"] == 118.0
        assert by_sponsor[B["membership_id"]]["level"] == 2
        assert by_sponsor[B["membership_id"]]["amount"] == 59.0
        assert by_sponsor[A["membership_id"]]["level"] == 3
        assert by_sponsor[A["membership_id"]]["amount"] == 23.6
        for r in purchase_rows:
            assert r["status"] == "pending"

    def test_commission_idempotency_on_verify_replay(self, sub_program, buy_program):
        s = _register()
        _make_active_green(s, sub_program["id"])
        b = _register(referral_id=s["membership_id"])
        # First order+verify
        o = requests.post(
            f"{API}/payments/order",
            headers=b["headers"],
            json={"program_id": buy_program["id"]},
        )
        assert o.status_code == 201, o.text
        oid = o.json()["order_id"]
        payload = {
            "razorpay_order_id": oid,
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{oid}",
        }
        r1 = requests.post(f"{API}/payments/verify", headers=b["headers"], json=payload)
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/payments/verify", headers=b["headers"], json=payload)
        assert r2.status_code == 200
        # Same purchase id
        assert r1.json()["purchase_id"] == r2.json()["purchase_id"]

        # Only ONE commission row for this purchase for sponsor s
        rows = requests.get(
            f"{API}/commissions/me",
            headers=s["headers"],
            params={"page_size": 100},
        ).json()
        matching = [
            r for r in rows["items"]
            if r["purchase_id"] == r1.json()["purchase_id"]
            and r["sponsor_membership_id"] == s["membership_id"]
        ]
        assert len(matching) == 1


# ============ 6. Global settings override ==================================
class TestGlobalSettings:
    def test_override_l1_percent_affects_new_purchase(self, admin_h, cat, sub_program):
        # Bump L1 to 20%
        r = requests.put(
            f"{API}/referrals/admin/settings",
            headers=admin_h,
            json={"commission_l1_percent": 20},
        )
        assert r.status_code == 200
        settings = r.json()
        assert float(settings["commission_l1_percent"]) == 20

        # Fresh purchase after change
        s = _register()
        _make_active_green(s, sub_program["id"])
        b = _register(referral_id=s["membership_id"])
        # New program to avoid duplicate-active guard from other tests
        prog = _create_program(
            admin_h, cat["id"], price=1000, gst_percent=18,
            is_subscription=False, level=None, name_prefix="OVR20"
        )
        v, _ = _buy_program(b, prog["id"])

        rows = requests.get(
            f"{API}/commissions/me",
            headers=s["headers"],
            params={"page_size": 100},
        ).json()
        row = next(r for r in rows["items"] if r["purchase_id"] == v["purchase_id"])
        assert row["level"] == 1
        # 20% of 1180 = 236
        assert row["amount"] == 236.0

        # Reset back to 10
        requests.put(
            f"{API}/referrals/admin/settings",
            headers=admin_h,
            json={"commission_l1_percent": 10},
        )


# ============ 7. Admin commissions (list + approve/reject/bulk-approve) =====
class TestAdminCommissions:
    def test_admin_list_with_filters(self, admin_h):
        r = requests.get(
            f"{API}/commissions/admin",
            headers=admin_h,
            params={"page_size": 10, "page": 1},
        )
        assert r.status_code == 200
        assert "items" in r.json()
        # status filter
        r2 = requests.get(
            f"{API}/commissions/admin",
            headers=admin_h,
            params={"status": "pending", "page_size": 5},
        )
        assert r2.status_code == 200
        for it in r2.json()["items"]:
            assert it["status"] == "pending"
        # level filter
        r3 = requests.get(
            f"{API}/commissions/admin",
            headers=admin_h,
            params={"level": 1, "page_size": 5},
        )
        assert r3.status_code == 200
        for it in r3.json()["items"]:
            assert it["level"] == 1

    def test_approve_reject_and_bulk_approve(self, admin_h, sub_program, buy_program):
        # seed 3 pending commissions
        pending_ids = []
        for _ in range(3):
            s = _register()
            _make_active_green(s, sub_program["id"])
            b = _register(referral_id=s["membership_id"])
            v, _ = _buy_program(b, buy_program["id"])
            rows = requests.get(
                f"{API}/commissions/me",
                headers=s["headers"],
                params={"page_size": 20},
            ).json()
            row = next(r for r in rows["items"] if r["purchase_id"] == v["purchase_id"])
            assert row["status"] == "pending"
            pending_ids.append(row["id"])

        # Approve first
        r_ap = requests.post(
            f"{API}/commissions/admin/{pending_ids[0]}/approve",
            headers=admin_h,
            json={"reason": "TEST_ok"},
        )
        assert r_ap.status_code == 200, r_ap.text
        assert r_ap.json()["status"] == "approved"

        # Second approve returns 409
        r_ap2 = requests.post(
            f"{API}/commissions/admin/{pending_ids[0]}/approve",
            headers=admin_h,
            json={"reason": "again"},
        )
        assert r_ap2.status_code == 409

        # Reject second
        r_rj = requests.post(
            f"{API}/commissions/admin/{pending_ids[1]}/reject",
            headers=admin_h,
            json={"reason": "TEST_bad"},
        )
        assert r_rj.status_code == 200
        assert r_rj.json()["status"] == "rejected"

        # Bulk approve the third (in a list)
        r_bulk = requests.post(
            f"{API}/commissions/admin/bulk-approve",
            headers=admin_h,
            json={"ids": [pending_ids[2]]},
        )
        assert r_bulk.status_code == 200
        assert r_bulk.json()["approved"] >= 1

    def test_admin_summary_shape(self, admin_h):
        r = requests.get(f"{API}/commissions/admin/summary", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        assert "buckets" in d
        for k in ("pending", "approved", "paid", "rejected"):
            assert k in d["buckets"]
            assert "amount" in d["buckets"][k]
            assert "count" in d["buckets"][k]
        assert "payable_now" in d
        # payable_now == approved.amount
        assert d["payable_now"] == d["buckets"]["approved"]["amount"]


# ============ 8. Payouts ====================================================
class TestPayouts:
    def _seed_approved_commission_for_user(self, admin_h, sub_program, buy_program):
        """Create sponsor S with green status, buyer B, purchase, then approve S's commission."""
        s = _register()
        _make_active_green(s, sub_program["id"])
        b = _register(referral_id=s["membership_id"])
        v, _ = _buy_program(b, buy_program["id"])
        rows = requests.get(
            f"{API}/commissions/me",
            headers=s["headers"],
            params={"page_size": 20},
        ).json()
        row = next(r for r in rows["items"] if r["purchase_id"] == v["purchase_id"])
        # Approve
        r_ap = requests.post(
            f"{API}/commissions/admin/{row['id']}/approve",
            headers=admin_h,
            json={"reason": "TEST_approve"},
        )
        assert r_ap.status_code == 200, r_ap.text
        return s, row

    def test_pending_by_user_group(self, admin_h, sub_program, buy_program):
        s, row = self._seed_approved_commission_for_user(admin_h, sub_program, buy_program)
        r = requests.get(
            f"{API}/payouts/admin/pending-by-user", headers=admin_h
        )
        assert r.status_code == 200
        items = r.json()["items"]
        match = [it for it in items if it["user_membership_id"] == s["membership_id"]]
        assert len(match) == 1, match
        m = match[0]
        assert m["amount"] >= row["amount"]
        assert row["id"] in m["commission_ids"]
        assert m["commission_count"] >= 1

    def test_payout_create_validations(self, admin_h, sub_program, buy_program):
        s, row = self._seed_approved_commission_for_user(admin_h, sub_program, buy_program)
        # 400 if commission_ids include one that doesn't belong to user_membership_id
        s2, row2 = self._seed_approved_commission_for_user(admin_h, sub_program, buy_program)
        r_bad = requests.post(
            f"{API}/payouts/admin",
            headers=admin_h,
            json={
                "user_membership_id": s["membership_id"],
                "commission_ids": [row["id"], row2["id"]],
                "method": "bank",
            },
        )
        assert r_bad.status_code == 400, r_bad.text

    def test_payout_full_lifecycle(self, admin_h, sub_program, buy_program):
        s, row = self._seed_approved_commission_for_user(admin_h, sub_program, buy_program)
        # Create payout
        r_cr = requests.post(
            f"{API}/payouts/admin",
            headers=admin_h,
            json={
                "user_membership_id": s["membership_id"],
                "commission_ids": [row["id"]],
                "method": "bank",
                "reference": "TEST_REF",
                "notes": "TEST",
            },
        )
        assert r_cr.status_code == 201, r_cr.text
        payout = r_cr.json()
        assert payout["status"] == "pending"
        assert payout["amount"] == row["amount"]
        # Commission's payout_id is now set
        my_rows = requests.get(
            f"{API}/commissions/me",
            headers=s["headers"],
            params={"page_size": 20},
        ).json()
        upd = next(r for r in my_rows["items"] if r["id"] == row["id"])
        assert upd["payout_id"] == payout["id"]
        assert upd["status"] == "approved"

        # Mark paid
        r_pd = requests.post(
            f"{API}/payouts/admin/{payout['id']}/mark-paid",
            headers=admin_h,
            json={"reference": "UTR12345", "notes": "TEST_paid"},
        )
        assert r_pd.status_code == 200, r_pd.text
        # Second mark-paid returns 409
        r_pd2 = requests.post(
            f"{API}/payouts/admin/{payout['id']}/mark-paid",
            headers=admin_h,
            json={"reference": "UTR12345"},
        )
        assert r_pd2.status_code == 409
        # Commission status == paid
        my_rows2 = requests.get(
            f"{API}/commissions/me",
            headers=s["headers"],
            params={"page_size": 20},
        ).json()
        upd2 = next(r for r in my_rows2["items"] if r["id"] == row["id"])
        assert upd2["status"] == "paid"

        # Cancel paid payout → 409
        r_cx = requests.post(
            f"{API}/payouts/admin/{payout['id']}/cancel", headers=admin_h
        )
        assert r_cx.status_code == 409

    def test_payout_cancel_clears_payout_id(self, admin_h, sub_program, buy_program):
        s, row = self._seed_approved_commission_for_user(admin_h, sub_program, buy_program)
        r_cr = requests.post(
            f"{API}/payouts/admin",
            headers=admin_h,
            json={
                "user_membership_id": s["membership_id"],
                "commission_ids": [row["id"]],
                "method": "bank",
            },
        )
        assert r_cr.status_code == 201
        payout = r_cr.json()
        # Cancel
        r_cx = requests.post(
            f"{API}/payouts/admin/{payout['id']}/cancel", headers=admin_h
        )
        assert r_cx.status_code == 200
        # commission payout_id cleared
        my_rows = requests.get(
            f"{API}/commissions/me",
            headers=s["headers"],
            params={"page_size": 20},
        ).json()
        upd = next(r for r in my_rows["items"] if r["id"] == row["id"])
        assert upd["payout_id"] is None
        assert upd["status"] == "approved"

    def test_user_payouts_only_own(self, admin_h, sub_program, buy_program):
        s, row = self._seed_approved_commission_for_user(admin_h, sub_program, buy_program)
        # create a payout
        r_cr = requests.post(
            f"{API}/payouts/admin",
            headers=admin_h,
            json={
                "user_membership_id": s["membership_id"],
                "commission_ids": [row["id"]],
                "method": "bank",
            },
        )
        assert r_cr.status_code == 201
        # Now fetch as user
        mine = requests.get(f"{API}/payouts/me", headers=s["headers"]).json()
        assert mine["total"] >= 1
        for it in mine["items"]:
            assert it["user_membership_id"] == s["membership_id"]


# ============ 9. Reports (5 PDFs + 400 unknown) =============================
class TestReports:
    def test_all_report_pdfs(self):
        u = _register()
        for kind in ("referral", "income", "downline", "subscription", "transaction"):
            r = requests.get(f"{API}/reports/{kind}", headers=u["headers"])
            assert r.status_code == 200, f"{kind} → {r.status_code} {r.text[:200]}"
            assert "application/pdf" in r.headers.get("Content-Type", "")
            assert r.content.startswith(b"%PDF"), f"{kind} not a PDF"
            assert len(r.content) > 1000

    def test_unknown_report_400(self):
        u = _register()
        r = requests.get(f"{API}/reports/unknown", headers=u["headers"])
        assert r.status_code == 400


# ============ 10. Settings roundtrip ========================================
class TestReferralSettings:
    def test_defaults_when_unset(self, admin_h):
        # GET returns keys with defaults populated
        r = requests.get(f"{API}/referrals/admin/settings", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        # These keys must be present in the response
        for k in (
            "commission_l1_percent",
            "commission_l2_percent",
            "commission_l3_percent",
            "commission_mode",
            "grace_period_days",
            "activity_sessions_required",
        ):
            assert k in d
        # Default sessions required
        assert int(d["activity_sessions_required"]) == 4

    def test_put_roundtrip(self, admin_h):
        r = requests.put(
            f"{API}/referrals/admin/settings",
            headers=admin_h,
            json={
                "commission_l2_percent": 7,
                "commission_l3_percent": 3,
                "grace_period_days": 5,
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert float(d["commission_l2_percent"]) == 7
        assert float(d["commission_l3_percent"]) == 3
        assert int(d["grace_period_days"]) == 5
        # Restore
        requests.put(
            f"{API}/referrals/admin/settings",
            headers=admin_h,
            json={
                "commission_l2_percent": 5,
                "commission_l3_percent": 2,
                "grace_period_days": 3,
            },
        )


# ============ 11. Auth guards ===============================================
class TestAuthGuards:
    def test_user_endpoints_require_jwt(self):
        for path in (
            "/activity/meter",
            "/activity/sessions/me",
            "/referrals/dashboard",
            "/referrals/team",
            "/referrals/share/qr",
            "/commissions/me",
            "/commissions/me/summary",
            "/payouts/me",
            "/reports/referral",
        ):
            r = requests.get(f"{API}{path}")
            assert r.status_code == 401, f"{path} expected 401 got {r.status_code}"

    def test_admin_endpoints_reject_user_token(self):
        u = _register()
        for path in (
            "/commissions/admin",
            "/commissions/admin/summary",
            "/payouts/admin",
            "/payouts/admin/pending-by-user",
            "/referrals/admin/settings",
        ):
            r = requests.get(f"{API}{path}", headers=u["headers"])
            assert r.status_code in (401, 403), (
                f"{path} expected 401/403 got {r.status_code}"
            )


# ============ 12. RED status via DB expiry manipulation ====================
class TestRedStatus:
    def test_red_status_when_subscription_expired(self, sub_program):
        """Manipulate DB to expire the subscription and confirm meter='red'."""
        from motor.motor_asyncio import AsyncIOMotorClient

        u = _register()
        sub_resp = _subscribe(u, sub_program["id"])
        sub_id = sub_resp["subscription_id"]

        async def _expire():
            client = AsyncIOMotorClient(
                os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            )
            db = client[os.environ.get("DB_NAME", "test_database")]
            past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
            # Match by user + subscription-sourced purchase
            await db.program_purchases.update_many(
                {
                    "user_membership_id": u["membership_id"],
                    "source": "subscription_mock",
                },
                {"$set": {"expiry_date": past}},
            )
            client.close()

        asyncio.get_event_loop().run_until_complete(_expire())

        m = requests.get(f"{API}/activity/meter", headers=u["headers"]).json()
        # Post-Activity-Meter-v2: an expired subscription with no other active
        # purchase resolves to `no_plan` (previously "red"). Both indicate the
        # user cannot earn commissions and must reactivate.
        assert m["status"] in ("red", "no_plan"), m


# ============ 13. Regression Phase 5 payments + Phase 4 =====================
class TestRegression:
    def test_phase5_payment_e2e(self, admin_h, cat):
        u = _register()
        prog = _create_program(
            admin_h, cat["id"], is_subscription=True, price=250, name_prefix="REGP5"
        )
        v, _ = _buy_program(u, prog["id"])
        # /payments/me contains it
        me = requests.get(f"{API}/payments/me", headers=u["headers"]).json()
        assert any(it["id"] == v["purchase_id"] for it in me["items"])
        # invoice PDF downloads
        r = requests.get(
            f"{API}/payments/invoice/{v['purchase_id']}", headers=u["headers"]
        )
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("Content-Type", "")

    def test_phase4_module_and_assessment(self, admin_h, cat):
        u = _register()
        prog = _create_program(
            admin_h, cat["id"], is_subscription=True, price=1, name_prefix="REGP4"
        )
        m1 = requests.post(
            f"{API}/modules/admin",
            headers=admin_h,
            json={
                "program_id": prog["id"],
                "module_number": 1,
                "name": "REGP4_M1",
                "sequential_unlock": True,
            },
        ).json()
        # Purchase via legacy
        rp = requests.post(
            f"{API}/programs/{prog['id']}/purchase",
            headers=u["headers"],
            json={"program_id": prog["id"]},
        )
        assert rp.status_code == 201, rp.text
        st = requests.get(
            f"{API}/programs/{prog['id']}/status", headers=u["headers"]
        )
        assert st.status_code == 200
        assert st.json()["has_access"] is True
        # Module complete
        rc = requests.post(
            f"{API}/progress/me/{prog['id']}/module/{m1['id']}/complete",
            headers=u["headers"],
            json={"time_spent_sec": 2},
        )
        assert rc.status_code == 200
        assert rc.json()["certificate"] is not None
        # /certificates/me
        cs = requests.get(f"{API}/certificates/me", headers=u["headers"])
        assert cs.status_code == 200
