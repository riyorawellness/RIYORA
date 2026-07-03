"""RIYORA WELLNESS — Phase 5 Backend Regression Suite (Razorpay Payment Engine).

Covers the new payments module in MOCK mode:
  * GET  /payments/config
  * POST /payments/order             (sequence gate, duplicate guard, breakdown, prefill)
  * POST /payments/verify            (signature happy/bad/idempotent)
  * GET  /programs/{id}/status       (has_access + active_purchase after verify)
  * GET  /payments/me                (paginated purchase history)
  * GET  /payments/invoice/{id}      (application/pdf, >1KB, file on disk)
  * POST /payments/subscription      (mock_sub_*, unlocks program access, 404 if not sub)
  * GET  /payments/subscription/me
  * POST /payments/subscription/{id}/cancel
  * POST /payments/webhook           (mock signature accepted)
  * Admin: transactions list + summary + refund (409 on double refund) + settings roundtrip
  * Auth: 401 without JWT, 403 for admin endpoints with user token
  * Regression: Phase 4 flows still work (register, admin CRUD, dashboard,
    legacy /programs/{id}/purchase, module complete, assessment submit, cert)

Mock signature contract: `mock_sig_<order_id>`.
"""
import os
import random
import uuid
from pathlib import Path

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


def _slug(prefix: str = "p5") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register_user(s):
    m = _rand_mobile()
    s.post(f"{API}/auth/send-otp", json={"mobile": m, "purpose": "register"})
    s.post(f"{API}/auth/verify-otp", json={"mobile": m, "purpose": "register", "code": DEV_OTP})
    r = s.post(f"{API}/auth/register", json={
        "full_name": "TEST_P5User",
        "mobile": m, "state": "KA", "city": "BLR",
        "referral_id": COMPANY_REF,
        "password": DEFAULT_PASSWORD, "confirm_password": DEFAULT_PASSWORD,
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return {
        "mobile": m,
        "membership_id": d["user"]["membership_id"],
        "full_name": d["user"].get("full_name", "TEST_P5User"),
        "access": d["tokens"]["access_token"],
    }


# ============ Fixtures ======================================================
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def admin_h(s):
    r = s.post(f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user(s):
    return _register_user(s)


@pytest.fixture(scope="module")
def user_h(user):
    return {"Authorization": f"Bearer {user['access']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def cat(admin_h):
    r = requests.post(f"{API}/categories/admin", headers=admin_h,
                      json={"name": "TEST_P5_Cat", "slug": _slug("cat"), "order_index": 995})
    assert r.status_code == 201, r.text
    return r.json()


def _create_program(admin_h, cat_id, price=1000, discount=0, gst_percent=None,
                    validity_days=30, is_subscription=False, level=None,
                    name_prefix="P5"):
    body = {
        "name": f"TEST_{name_prefix}_{uuid.uuid4().hex[:6]}",
        "slug": _slug(name_prefix.lower()),
        "price": price,
        "discount": discount,
        "validity_days": validity_days,
        "category_id": cat_id,
        "is_subscription": is_subscription,
    }
    if gst_percent is not None:
        body["gst_percent"] = gst_percent
    if level is not None:
        body["level"] = level
    r = requests.post(f"{API}/programs/admin", headers=admin_h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ============ /payments/config =============================================
class TestPaymentConfig:
    def test_requires_auth(self):
        r = requests.get(f"{API}/payments/config")
        assert r.status_code == 401

    def test_config_returns_key_and_mock_flag(self, user_h):
        r = requests.get(f"{API}/payments/config", headers=user_h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["is_mock"] is True
        assert d["currency"] == "INR"
        assert d["key_id"]  # non-empty (rzp_test_mock in mock mode)
        assert "checkout_theme" in d and d["checkout_theme"]


# ============ /payments/order ===============================================
class TestCreateOrder:
    def test_order_happy_path_with_breakdown_and_prefill(self, admin_h, user, user_h, cat):
        prog = _create_program(admin_h, cat["id"], price=1000, discount=100,
                               gst_percent=18, validity_days=45, is_subscription=True,
                               name_prefix="ORD")
        r = requests.post(f"{API}/payments/order", headers=user_h,
                          json={"program_id": prog["id"]})
        assert r.status_code == 201, r.text
        d = r.json()
        # mock order id
        assert d["order_id"].startswith("mock_ord_")
        assert d["is_mock"] is True
        assert d["currency"] == "INR"
        # breakdown maths: taxable=900, gst=162, total=1062, paise=106200
        b = d["breakdown"]
        assert b["price"] == 1000
        assert b["discount"] == 100
        assert b["taxable"] == 900
        assert b["gst_percent"] == 18
        assert b["gst_amount"] == 162
        assert b["total"] == 1062
        assert d["amount_paise"] == 106200
        assert d["amount_rupees"] == 1062
        # prefill has user's mobile + name
        assert d["prefill"]["contact"] == user["mobile"]
        assert d["prefill"]["name"]  # full_name from JWT payload
        # program echoed
        assert d["program"]["id"] == prog["id"]
        assert d["program"]["validity_days"] == 45

    def test_requires_auth(self, admin_h, cat):
        prog = _create_program(admin_h, cat["id"], is_subscription=True, name_prefix="NOAUTH")
        r = requests.post(f"{API}/payments/order", json={"program_id": prog["id"]})
        assert r.status_code == 401

    def test_program_not_found(self, user_h):
        r = requests.post(f"{API}/payments/order", headers=user_h,
                          json={"program_id": "does-not-exist-xyz"})
        assert r.status_code == 404

    def test_blocked_by_sequence_gate(self, admin_h, s, cat):
        """User must complete Level N-1 before purchasing Level N."""
        # Program level cap is 10 in the pydantic model; use 5 & 6 which are
        # unlikely to clash with seeded L1/L2. If an L5 program from a prior
        # run is already present it is still fine — the fresh user has not
        # completed it either → sequence gate still blocks.
        L1_LVL, L2_LVL = 5, 6
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        _l1 = _create_program(admin_h, cat["id"], level=L1_LVL, name_prefix="ORDL1",
                              is_subscription=False)
        _l2 = _create_program(admin_h, cat["id"], level=L2_LVL, name_prefix="ORDL2",
                              is_subscription=False)
        r = requests.post(f"{API}/payments/order", headers=_h,
                          json={"program_id": _l2["id"]})
        assert r.status_code == 403, r.text
        # Detail comes from program_engine.check_purchase_allowed
        detail = r.json().get("detail", "")
        assert "certificate" in detail.lower() or "complete" in detail.lower()

    def test_blocked_when_already_active(self, admin_h, s, cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, cat["id"], is_subscription=True,
                               name_prefix="DUP", price=500)
        # First order → verify → active
        r1 = requests.post(f"{API}/payments/order", headers=_h,
                           json={"program_id": prog["id"]})
        assert r1.status_code == 201, r1.text
        oid = r1.json()["order_id"]
        r2 = requests.post(f"{API}/payments/verify", headers=_h, json={
            "razorpay_order_id": oid,
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{oid}",
        })
        assert r2.status_code == 200
        # Second order should be blocked with 409
        r3 = requests.post(f"{API}/payments/order", headers=_h,
                           json={"program_id": prog["id"]})
        assert r3.status_code == 409, r3.text
        assert "already" in r3.json().get("detail", "").lower()


# ============ /payments/verify ==============================================
class TestVerifyPayment:
    def _order(self, admin_h, user_h, cat, **prog_kwargs):
        prog = _create_program(admin_h, cat["id"], is_subscription=True,
                               name_prefix="VER", **prog_kwargs)
        r = requests.post(f"{API}/payments/order", headers=user_h,
                          json={"program_id": prog["id"]})
        assert r.status_code == 201
        return prog, r.json()

    def test_bad_signature_rejected_and_no_purchase_row(self, admin_h, s, cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog, order = self._order(admin_h, _h, cat, price=200)
        r = requests.post(f"{API}/payments/verify", headers=_h, json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": "totally_wrong_sig",
        })
        assert r.status_code == 400, r.text
        assert "invalid" in r.json()["detail"].lower()
        # No purchase created — /payments/me should not include this program
        me = requests.get(f"{API}/payments/me", headers=_h).json()
        assert all(it["program_id"] != prog["id"] for it in me["items"])
        # And has_access on that program should be False
        st = requests.get(f"{API}/programs/{prog['id']}/status", headers=_h).json()
        assert st["has_access"] is False

    def test_good_signature_creates_purchase_and_invoice(self, admin_h, s, cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog, order = self._order(admin_h, _h, cat, price=500, discount=50, validity_days=60)
        oid = order["order_id"]
        r = requests.post(f"{API}/payments/verify", headers=_h, json={
            "razorpay_order_id": oid,
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{oid}",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["success"] is True
        assert d["invoice_number"].startswith("INV-")
        assert d["expiry_date"] > d.get("purchase_date", "")
        assert d["program_id"] == prog["id"]
        # Purchase visible on /programs/{id}/status
        st = requests.get(f"{API}/programs/{prog['id']}/status", headers=_h).json()
        assert st["has_access"] is True
        assert st["active_purchase"] is not None
        # PDF file exists on disk
        inv_path = Path(f"/app/backend/invoices/{d['invoice_number']}.pdf")
        assert inv_path.exists(), f"Invoice PDF missing at {inv_path}"
        assert inv_path.stat().st_size > 1000

    def test_verify_idempotent(self, admin_h, s, cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog, order = self._order(admin_h, _h, cat, price=300)
        oid = order["order_id"]
        payload = {
            "razorpay_order_id": oid,
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{oid}",
        }
        r1 = requests.post(f"{API}/payments/verify", headers=_h, json=payload).json()
        r2 = requests.post(f"{API}/payments/verify", headers=_h, json=payload).json()
        # Same purchase_id + invoice on replay (idempotent)
        assert r1["purchase_id"] == r2["purchase_id"]
        assert r1["invoice_number"] == r2["invoice_number"]


# ============ /payments/me + invoice PDF ====================================
class TestPaymentsMeAndInvoice:
    def test_me_lists_purchase_and_invoice_pdf_downloads(self, admin_h, s, cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, cat["id"], is_subscription=True,
                               price=250, name_prefix="MEIV")
        order = requests.post(f"{API}/payments/order", headers=_h,
                              json={"program_id": prog["id"]}).json()
        oid = order["order_id"]
        r = requests.post(f"{API}/payments/verify", headers=_h, json={
            "razorpay_order_id": oid,
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{oid}",
        })
        assert r.status_code == 200
        purchase_id = r.json()["purchase_id"]
        invoice_number = r.json()["invoice_number"]

        me = requests.get(f"{API}/payments/me", headers=_h).json()
        assert me["total"] >= 1
        entry = next((it for it in me["items"] if it["id"] == purchase_id), None)
        assert entry is not None
        assert entry["invoice_number"] == invoice_number
        assert entry["program"]["id"] == prog["id"]
        assert entry["program"]["name"] == prog["name"]
        assert "total" in entry and entry["total"] >= 0
        assert "expiry_date" in entry

        # Invoice PDF download
        r_pdf = requests.get(f"{API}/payments/invoice/{purchase_id}", headers=_h)
        assert r_pdf.status_code == 200
        assert "application/pdf" in r_pdf.headers.get("Content-Type", "")
        assert len(r_pdf.content) > 1000


# ============ /payments/subscription ========================================
class TestSubscription:
    def test_subscription_creates_row_and_unlocks_program(self, admin_h, s, cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, cat["id"], is_subscription=True,
                               price=999, validity_days=30, name_prefix="SUB")
        r = requests.post(f"{API}/payments/subscription", headers=_h,
                          json={"program_id": prog["id"], "plan": "monthly"})
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["subscription_id"].startswith("mock_sub_")
        assert d["status"] == "active"
        assert d["plan"] == "monthly"
        assert d["is_mock"] is True

        # Program access should be unlocked (matching program_purchases row)
        st = requests.get(f"{API}/programs/{prog['id']}/status", headers=_h).json()
        assert st["has_access"] is True
        assert st["active_purchase"] is not None

        # Sub list contains it
        lst = requests.get(f"{API}/payments/subscription/me", headers=_h).json()
        ids = [x["subscription_id"] for x in lst["items"]]
        assert d["subscription_id"] in ids

        # Cancel — status becomes cancelled
        sub_pk = [x for x in lst["items"] if x["subscription_id"] == d["subscription_id"]][0]["id"]
        rc = requests.post(f"{API}/payments/subscription/{sub_pk}/cancel", headers=_h)
        assert rc.status_code == 200
        assert rc.json()["success"] is True
        lst2 = requests.get(f"{API}/payments/subscription/me", headers=_h).json()
        row = [x for x in lst2["items"] if x["subscription_id"] == d["subscription_id"]][0]
        assert row["status"] == "cancelled"

    def test_subscription_404_when_program_not_subscription(self, admin_h, s, cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, cat["id"], is_subscription=False,
                               price=100, name_prefix="NOTSUB")
        r = requests.post(f"{API}/payments/subscription", headers=_h,
                          json={"program_id": prog["id"], "plan": "monthly"})
        assert r.status_code == 404, r.text


# ============ /payments/webhook =============================================
class TestWebhook:
    def test_mock_signature_accepted(self):
        r = requests.post(f"{API}/payments/webhook",
                          headers={"X-Razorpay-Signature": "mock_test",
                                   "Content-Type": "application/json"},
                          json={"event": "payment.captured"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "processed"


# ============ Admin transactions/summary/refund/settings ===================
class TestAdminPayments:
    def test_admin_endpoints_require_admin_token(self, user_h):
        # user JWT → 403 on admin routes
        r = requests.get(f"{API}/payments/admin/transactions", headers=user_h)
        assert r.status_code in (401, 403)
        r = requests.get(f"{API}/payments/admin/summary", headers=user_h)
        assert r.status_code in (401, 403)
        r = requests.get(f"{API}/payments/admin/settings", headers=user_h)
        assert r.status_code in (401, 403)

    def test_admin_transactions_list_and_filter(self, admin_h, s, cat):
        # Seed a fresh completed purchase
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, cat["id"], is_subscription=True,
                               price=111, name_prefix="ADMTXN")
        order = requests.post(f"{API}/payments/order", headers=_h,
                              json={"program_id": prog["id"]}).json()
        oid = order["order_id"]
        v = requests.post(f"{API}/payments/verify", headers=_h, json={
            "razorpay_order_id": oid,
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{oid}",
        }).json()

        # List
        r = requests.get(f"{API}/payments/admin/transactions", headers=admin_h)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] >= 1
        assert "items" in d
        # Every entry has user + program embedded
        sample = d["items"][0]
        assert "user" in sample and "program" in sample

        # q search by invoice number
        r2 = requests.get(f"{API}/payments/admin/transactions",
                          headers=admin_h, params={"q": v["invoice_number"]})
        assert r2.status_code == 200
        assert any(it["invoice_number"] == v["invoice_number"] for it in r2.json()["items"])

        # status filter
        r3 = requests.get(f"{API}/payments/admin/transactions",
                          headers=admin_h, params={"status": "active"})
        assert r3.status_code == 200
        for it in r3.json()["items"]:
            assert it["status"] == "active"

    def test_admin_summary_shape(self, admin_h):
        r = requests.get(f"{API}/payments/admin/summary", headers=admin_h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "total_revenue" in d and isinstance(d["total_revenue"], (int, float))
        assert "total_transactions" in d and isinstance(d["total_transactions"], int)
        assert "buckets" in d
        for k in ("active", "expired", "cancelled", "refunded"):
            assert k in d["buckets"]
            assert "count" in d["buckets"][k]
            assert "revenue" in d["buckets"][k]

    def test_admin_refund_and_double_refund_409(self, admin_h, s, cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, cat["id"], is_subscription=True,
                               price=222, name_prefix="ADMREF")
        order = requests.post(f"{API}/payments/order", headers=_h,
                              json={"program_id": prog["id"]}).json()
        oid = order["order_id"]
        v = requests.post(f"{API}/payments/verify", headers=_h, json={
            "razorpay_order_id": oid,
            "razorpay_payment_id": f"mock_pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": f"mock_sig_{oid}",
        }).json()
        pid = v["purchase_id"]

        r1 = requests.post(f"{API}/payments/admin/transactions/{pid}/refund",
                           headers=admin_h, json={"reason": "TEST_refund"})
        assert r1.status_code == 200, r1.text
        assert r1.json()["success"] is True

        # Confirm status=refunded on admin list
        r_list = requests.get(f"{API}/payments/admin/transactions",
                              headers=admin_h, params={"q": v["invoice_number"]}).json()
        row = [it for it in r_list["items"] if it["id"] == pid][0]
        assert row["status"] == "refunded"
        assert row.get("refund_reason") == "TEST_refund"
        assert row.get("refunded_by")

        # Double refund → 409
        r2 = requests.post(f"{API}/payments/admin/transactions/{pid}/refund",
                           headers=admin_h, json={"reason": "again"})
        assert r2.status_code == 409

    def test_admin_settings_roundtrip(self, admin_h):
        # GET current
        r = requests.get(f"{API}/payments/admin/settings", headers=admin_h)
        assert r.status_code == 200
        # PUT changes
        new_prefix = f"T{uuid.uuid4().hex[:3].upper()}"
        payload = {
            "default_gst_percent": 12,
            "default_validity_days": 400,
            "company_gst_number": "27AAAAA0000A1Z5",
            "invoice_prefix": new_prefix,
        }
        r2 = requests.put(f"{API}/payments/admin/settings", headers=admin_h, json=payload)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert float(d["default_gst_percent"]) == 12
        assert int(d["default_validity_days"]) == 400
        assert d["company_gst_number"] == "27AAAAA0000A1Z5"
        assert d["invoice_prefix"] == new_prefix
        # GET again — persists
        r3 = requests.get(f"{API}/payments/admin/settings", headers=admin_h).json()
        assert r3["invoice_prefix"] == new_prefix

        # Restore defaults (best-effort)
        requests.put(f"{API}/payments/admin/settings", headers=admin_h, json={
            "default_gst_percent": 18,
            "default_validity_days": 365,
            "invoice_prefix": "INV",
        })


# ============ Regression: Phase 4 legacy flows still work ==================
class TestPhase4Regression:
    def test_legacy_direct_purchase_still_works(self, admin_h, s, cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, cat["id"], is_subscription=True,
                               price=1, name_prefix="LEGACY")
        m1 = requests.post(f"{API}/modules/admin", headers=admin_h, json={
            "program_id": prog["id"], "module_number": 1, "name": "TEST_M1",
            "sequential_unlock": True,
        }).json()
        # Legacy purchase
        r = requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                          json={"program_id": prog["id"]})
        assert r.status_code == 201, r.text
        # Dashboard reflects it
        rd = requests.get(f"{API}/programs/me/dashboard", headers=_h)
        assert rd.status_code == 200
        assert any(e["program"]["id"] == prog["id"] for e in rd.json()["purchased"])
        # Module complete + cert flow still works
        rc = requests.post(f"{API}/progress/me/{prog['id']}/module/{m1['id']}/complete",
                           headers=_h, json={"time_spent_sec": 3})
        assert rc.status_code == 200
        assert rc.json()["progress"]["certificate_eligible"] is True
        assert rc.json()["certificate"] is not None
        assert rc.json()["certificate"]["certificate_number"].startswith("RW-CERT-")
        # /certificates/me
        r_cert = requests.get(f"{API}/certificates/me", headers=_h)
        assert r_cert.status_code == 200
