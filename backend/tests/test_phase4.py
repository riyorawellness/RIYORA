"""RIYORA WELLNESS — Phase 4 Backend Regression Suite (Programs Engine).

Covers Phase 4 business-logic layer:
  * Program sequence gating (Level N requires Level N-1 completed + cert)
  * Subscription programs bypass sequence
  * Purchase creation (metadata + expiry) & invoice uniqueness
  * Validity engine (mark_expired_purchases via dashboard)
  * Sequential module unlock via /modules/me/by-program/{id}
  * /me/{program_id}/module/{module_id}/complete idempotency, %, cert-eligible
  * Auto certificate on all modules complete (RW-CERT-*), no duplicate
  * Certificate + Assessment interplay (must pass assessment first)
  * Assessment attempts_allowed enforcement (+ passed bypass)
  * Assessment randomize + correct_index stripped from GET
  * Content token issue/stream (302, no-store, inline) + 401 for bad token
  * Continue-learning + Dashboard buckets

Uses REACT_APP_BACKEND_URL and Mongo direct access for expiry manipulation.
Dev OTP = 123456. Company referral = RW000000. Admin: 9999999999 / Admin@12345.
"""
import os
import random
import time
import uuid
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient

# ---- Load public URL from frontend/.env ------------------------------------
_env = Path("/app/frontend/.env")
for _ln in _env.read_text().splitlines():
    if _ln.startswith("REACT_APP_BACKEND_URL"):
        os.environ["REACT_APP_BACKEND_URL"] = _ln.split("=", 1)[1].strip()

# Backend Mongo (for direct-write helpers only — no seed mutation).
_bknd_env = Path("/app/backend/.env")
for _ln in _bknd_env.read_text().splitlines():
    if _ln.startswith("MONGO_URL"):
        os.environ["MONGO_URL"] = _ln.split("=", 1)[1].strip().strip('"')
    if _ln.startswith("DB_NAME"):
        os.environ["DB_NAME"] = _ln.split("=", 1)[1].strip().strip('"')

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"
COMPANY_REF = "RW000000"
DEV_OTP = "123456"
DEFAULT_PASSWORD = "Passw0rd!"


def _rand_mobile() -> str:
    return random.choice("6789") + "".join(random.choices("0123456789", k=9))


def _slug(prefix: str = "p4") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


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


def _register_user(s):
    m = _rand_mobile()
    s.post(f"{API}/auth/send-otp", json={"mobile": m, "purpose": "register"})
    s.post(f"{API}/auth/verify-otp", json={"mobile": m, "purpose": "register", "code": DEV_OTP})
    r = s.post(f"{API}/auth/register", json={
        "full_name": "TEST_P4User",
        "mobile": m, "state": "KA", "city": "BLR",
        "referral_id": COMPANY_REF,
        "password": DEFAULT_PASSWORD, "confirm_password": DEFAULT_PASSWORD,
    })
    assert r.status_code == 200, r.text
    d = r.json()
    return {"mobile": m, "membership_id": d["user"]["membership_id"],
            "access": d["tokens"]["access_token"]}


@pytest.fixture(scope="module")
def user(s):
    return _register_user(s)


@pytest.fixture(scope="module")
def user_h(user):
    return {"Authorization": f"Bearer {user['access']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest.fixture(scope="module")
def foundation_cat(admin_h):
    """Create an isolated TEST category so tests don't collide with seeded rows."""
    r = requests.post(f"{API}/categories/admin", headers=admin_h,
                      json={"name": "TEST_P4_Cat", "slug": _slug("cat"),
                            "order_index": 990})
    assert r.status_code == 201, r.text
    return r.json()


def _create_program(admin_h, cat_id, level=None, is_subscription=False,
                    validity_days=30, price=1, name_prefix="P4"):
    body = {
        "name": f"TEST_{name_prefix}_{uuid.uuid4().hex[:6]}",
        "slug": _slug(name_prefix.lower()),
        "price": price,
        "validity_days": validity_days,
        "category_id": cat_id,
        "is_subscription": is_subscription,
    }
    if level is not None:
        body["level"] = level
    r = requests.post(f"{API}/programs/admin", headers=admin_h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _create_module(admin_h, program_id, module_number, name=None, video_url=None,
                   audio_url=None, pdf_url=None, mtype=None):
    body = {
        "program_id": program_id,
        "module_number": module_number,
        "name": name or f"TEST_M{module_number}",
        "sequential_unlock": True,
    }
    if video_url:
        body["video_url"] = video_url
    if audio_url:
        body["audio_url"] = audio_url
    if pdf_url:
        body["pdf_url"] = pdf_url
    if mtype:
        body["type"] = mtype
    r = requests.post(f"{API}/modules/admin", headers=admin_h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ============ Program-sequence gating =======================================
class TestSequenceGate:
    def test_l2_blocked_until_l1_done(self, admin_h, user_h, foundation_cat, s, mongo):
        # Unique level pair — avoid collisions with prior levels.
        # We use a helper user to keep isolated.
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}

        # NOTE: `_prev_level_program` uses find_one which returns the first
        # match at a given level. Production seeds L1="Chitta Shuddhi" and
        # L2="Prana Activation" so we pick out-of-band levels (8→9). Also
        # deactivate any residual L8/L9 programs left over from prior test
        # runs so this test's prerequisite is unambiguous.
        L1_LVL, L2_LVL = 8, 9
        mongo.programs.update_many(
            {"level": {"$in": [L1_LVL, L2_LVL]}, "deleted_at": None},
            {"$set": {"is_active": False}},
        )
        l1 = _create_program(admin_h, foundation_cat["id"], level=L1_LVL, name_prefix="L1")
        l2 = _create_program(admin_h, foundation_cat["id"], level=L2_LVL, name_prefix="L2")

        # Eligibility for L2 = false, reason mentions L1 name (or any existing L1).
        r = requests.get(f"{API}/programs/{l2['id']}/eligibility", headers=_h)
        assert r.status_code == 200
        d = r.json()
        assert d["eligible"] is False, d
        assert d["reason"] and ("Level 1" in d["reason"] or "L1" in d["reason"] or "certificate" in d["reason"].lower())

        # POST /purchase => 403 same reason
        r2 = requests.post(f"{API}/programs/{l2['id']}/purchase", headers=_h,
                           json={"program_id": l2["id"]})
        assert r2.status_code == 403, r2.text

        # Give user L1 purchase (via admin purchases route so bypass) → complete → cert.
        pur = requests.post(f"{API}/purchases/admin", headers=admin_h, json={
            "user_membership_id": _u["membership_id"],
            "program_id": l1["id"],
            "price_paid": 1, "total": 1,
            "invoice_number": f"INV-{uuid.uuid4().hex[:10].upper()}",
            "status": "active",
        })
        assert pur.status_code == 201, pur.text
        # Also insert program_purchases row so validity engine sees it (Phase 4
        # uses `program_purchases` collection separately from admin `/purchases`).
        # NOTE: Phase 4 uses collection `program_purchases`; admin route writes
        # to `purchases`. Confirm by calling /programs/{L1}/purchase after we
        # mark the sequence bypass isn't needed for L1. But L1 has level=1,
        # its prev is level=0 (subscription check) — no seed for level 0 =>
        # allowed = True.
        r_l1p = requests.post(f"{API}/programs/{l1['id']}/purchase", headers=_h,
                              json={"program_id": l1["id"]})
        assert r_l1p.status_code == 201, r_l1p.text

        # Create one module & complete it → cert eligible with no assessment.
        m1 = _create_module(admin_h, l1["id"], 1)
        r_c = requests.post(f"{API}/progress/me/{l1['id']}/module/{m1['id']}/complete",
                            headers=_h, json={"time_spent_sec": 5})
        assert r_c.status_code == 200, r_c.text
        assert r_c.json()["progress"]["certificate_eligible"] is True
        assert r_c.json()["certificate"] is not None
        assert r_c.json()["certificate"]["certificate_number"].startswith("RW-CERT-")

        # Now L2 eligibility flips true.
        r3 = requests.get(f"{API}/programs/{l2['id']}/eligibility", headers=_h)
        assert r3.status_code == 200
        assert r3.json()["eligible"] is True, r3.json()

        # And purchase succeeds.
        r4 = requests.post(f"{API}/programs/{l2['id']}/purchase", headers=_h,
                           json={"program_id": l2["id"]})
        assert r4.status_code == 201, r4.text
        d4 = r4.json()
        assert d4["invoice_number"].startswith("INV-")
        assert d4["status"] == "active"
        assert d4["expiry_date"] and d4["expiry_date"] > d4["purchase_date"]

    def test_subscription_bypasses_sequence(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        sub = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                              name_prefix="SUB", validity_days=30)
        r = requests.get(f"{API}/programs/{sub['id']}/eligibility", headers=_h)
        assert r.status_code == 200
        assert r.json()["eligible"] is True
        r2 = requests.post(f"{API}/programs/{sub['id']}/purchase", headers=_h,
                           json={"program_id": sub["id"]})
        assert r2.status_code == 201, r2.text


# ============ Purchase creation =============================================
class TestPurchaseCreation:
    def test_purchase_creates_expiry_and_invoice(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               validity_days=90, name_prefix="PUR")
        r = requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                          json={"program_id": prog["id"], "price_paid": 100,
                                "discount": 0, "gst_amount": 18, "total": 118})
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["invoice_number"].startswith("INV-")
        assert d["status"] == "active"
        assert d["expiry_date"] > d["purchase_date"]
        assert d["user_membership_id"] == _u["membership_id"]
        assert d["price_paid"] == 100
        assert d["total"] == 118


# ============ Validity engine ===============================================
class TestValidityEngine:
    def test_expire_moves_to_expired_bucket(self, admin_h, s, foundation_cat, mongo):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               validity_days=30, name_prefix="EXP")
        r = requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                          json={"program_id": prog["id"]})
        assert r.status_code == 201
        pur = r.json()

        # Direct-write to Mongo: set expiry to the past.
        res = mongo.program_purchases.update_one(
            {"id": pur["id"]},
            {"$set": {"expiry_date": "2020-01-01T00:00:00+00:00"}},
        )
        assert res.matched_count == 1

        # Hit dashboard — engine should flip status and put in 'expired'.
        r2 = requests.get(f"{API}/programs/me/dashboard", headers=_h)
        assert r2.status_code == 200
        d = r2.json()
        assert "expired" in d
        ids = [e["program"]["id"] for e in d["expired"]]
        assert prog["id"] in ids, d
        # And in Mongo, status should now be 'expired'
        row = mongo.program_purchases.find_one({"id": pur["id"]})
        assert row["status"] == "expired"


# ============ Sequential module unlock ======================================
class TestSequentialUnlock:
    def test_unlock_progression_and_block(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               validity_days=30, name_prefix="SEQ")
        m1 = _create_module(admin_h, prog["id"], 1)
        m2 = _create_module(admin_h, prog["id"], 2)
        m3 = _create_module(admin_h, prog["id"], 3)
        assert requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                             json={"program_id": prog["id"]}).status_code == 201

        # Initial: m1 unlocked, m2/m3 locked.
        r = requests.get(f"{API}/modules/me/by-program/{prog['id']}", headers=_h)
        assert r.status_code == 200
        d = r.json()
        assert d["has_access"] is True
        by_num = {m["module_number"]: m for m in d["modules"]}
        assert by_num[1]["is_unlocked"] is True
        assert by_num[2]["is_unlocked"] is False
        assert by_num[3]["is_unlocked"] is False

        # Try to complete m3 before m2 → 403
        r_bad = requests.post(f"{API}/progress/me/{prog['id']}/module/{m3['id']}/complete",
                              headers=_h, json={"time_spent_sec": 1})
        assert r_bad.status_code == 403
        assert "previous" in r_bad.json()["detail"].lower()

        # Complete m1 → m2 unlocks
        r_c = requests.post(f"{API}/progress/me/{prog['id']}/module/{m1['id']}/complete",
                            headers=_h, json={"time_spent_sec": 5})
        assert r_c.status_code == 200
        r2 = requests.get(f"{API}/modules/me/by-program/{prog['id']}", headers=_h)
        by_num = {m["module_number"]: m for m in r2.json()["modules"]}
        assert by_num[1]["is_completed"] is True
        assert by_num[2]["is_unlocked"] is True
        assert by_num[3]["is_unlocked"] is False

    def test_no_access_without_purchase(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               validity_days=30, name_prefix="NOACC")
        _create_module(admin_h, prog["id"], 1)
        r = requests.get(f"{API}/modules/me/by-program/{prog['id']}", headers=_h)
        assert r.status_code == 200
        d = r.json()
        assert d["has_access"] is False
        assert all(m["is_unlocked"] is False for m in d["modules"])

        # Content token → 403
        r2 = requests.post(f"{API}/content/token", headers=_h, params={
            "program_id": prog["id"], "module_id": d["modules"][0]["id"],
            "resource": "video",
        })
        assert r2.status_code == 403
        assert "active purchase" in r2.json()["detail"].lower()


# ============ Progress + Certificate ========================================
class TestProgressCertificate:
    def test_idempotent_complete_and_cert_issue(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               validity_days=30, name_prefix="CERT")
        m1 = _create_module(admin_h, prog["id"], 1)
        m2 = _create_module(admin_h, prog["id"], 2)
        requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                      json={"program_id": prog["id"]})

        # Complete m1 twice → idempotent
        r1 = requests.post(f"{API}/progress/me/{prog['id']}/module/{m1['id']}/complete",
                          headers=_h, json={"time_spent_sec": 10})
        assert r1.status_code == 200
        assert r1.json()["progress"]["percentage"] == 50.0
        assert r1.json()["certificate"] is None
        r1b = requests.post(f"{API}/progress/me/{prog['id']}/module/{m1['id']}/complete",
                            headers=_h, json={"time_spent_sec": 5})
        assert r1b.status_code == 200
        # Same module, no double-count
        assert r1b.json()["progress"]["percentage"] == 50.0
        assert len(r1b.json()["progress"]["completed_modules"]) == 1
        # time_spent_sec accumulates
        assert r1b.json()["progress"]["time_spent_sec"] >= 15

        # Complete m2 → 100%, cert issued
        r2 = requests.post(f"{API}/progress/me/{prog['id']}/module/{m2['id']}/complete",
                           headers=_h, json={"time_spent_sec": 7})
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["progress"]["percentage"] == 100.0
        assert d2["progress"]["certificate_eligible"] is True
        assert d2["progress"]["completion_date"]
        assert d2["certificate"] is not None
        cert_no = d2["certificate"]["certificate_number"]
        assert cert_no.startswith("RW-CERT-")
        assert d2["certificate"]["verification_number"]
        assert d2["certificate"]["status"] == "issued"

        # Re-complete m2 → no duplicate cert
        r3 = requests.post(f"{API}/progress/me/{prog['id']}/module/{m2['id']}/complete",
                           headers=_h, json={"time_spent_sec": 1})
        assert r3.status_code == 200
        assert r3.json()["certificate"]["certificate_number"] == cert_no

    def test_cert_requires_assessment_pass(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               validity_days=30, name_prefix="CERTAS")
        m1 = _create_module(admin_h, prog["id"], 1)
        # Assessment on this program (module_id doesn't matter for cert-gate)
        assess = requests.post(f"{API}/assessments/admin", headers=admin_h, json={
            "module_id": m1["id"], "program_id": prog["id"], "title": "TEST_As",
            "questions": [
                {"question": "q1", "options": ["a", "b"], "correct_index": 0},
                {"question": "q2", "options": ["x", "y"], "correct_index": 1},
            ],
            "passing_marks": 2, "attempts_allowed": 3,
        }).json()

        requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                      json={"program_id": prog["id"]})

        # Complete m1 (only module) → percentage 100 but NO cert (assessment gate).
        r = requests.post(f"{API}/progress/me/{prog['id']}/module/{m1['id']}/complete",
                          headers=_h, json={"time_spent_sec": 1})
        assert r.status_code == 200
        assert r.json()["progress"]["certificate_eligible"] is True
        assert r.json()["certificate"] is None, "Cert should NOT issue without assessment pass"

        # Submit failing → still no cert
        r_fail = requests.post(f"{API}/assessments/{assess['id']}/submit", headers=_h,
                               json={"assessment_id": assess["id"], "answers": [1, 0]})
        assert r_fail.status_code == 200
        assert r_fail.json()["result"]["passed"] is False
        assert r_fail.json()["certificate"] is None

        # Submit passing → cert
        r_pass = requests.post(f"{API}/assessments/{assess['id']}/submit", headers=_h,
                               json={"assessment_id": assess["id"], "answers": [0, 1]})
        assert r_pass.status_code == 200
        assert r_pass.json()["result"]["passed"] is True
        assert r_pass.json()["certificate"] is not None
        assert r_pass.json()["certificate"]["certificate_number"].startswith("RW-CERT-")


# ============ Assessment attempts + randomize + strip =======================
class TestAssessmentEngine:
    def test_attempts_allowed_enforced(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               name_prefix="ATT")
        m1 = _create_module(admin_h, prog["id"], 1)
        a = requests.post(f"{API}/assessments/admin", headers=admin_h, json={
            "module_id": m1["id"], "program_id": prog["id"], "title": "TEST_At",
            "questions": [{"question": "q", "options": ["a", "b"], "correct_index": 0}],
            "passing_marks": 1, "attempts_allowed": 2,
        }).json()

        # 2 failing attempts
        for _ in range(2):
            r = requests.post(f"{API}/assessments/{a['id']}/submit", headers=_h,
                              json={"assessment_id": a["id"], "answers": [1]})
            assert r.status_code == 200
            assert r.json()["result"]["passed"] is False
        # 3rd → 429
        r3 = requests.post(f"{API}/assessments/{a['id']}/submit", headers=_h,
                           json={"assessment_id": a["id"], "answers": [1]})
        assert r3.status_code == 429, r3.text
        assert "attempts remaining" in r3.json()["detail"].lower()

    def test_passed_bypasses_attempt_limit(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               name_prefix="PBP")
        m1 = _create_module(admin_h, prog["id"], 1)
        a = requests.post(f"{API}/assessments/admin", headers=admin_h, json={
            "module_id": m1["id"], "program_id": prog["id"], "title": "TEST_PB",
            "questions": [{"question": "q", "options": ["a", "b"], "correct_index": 0}],
            "passing_marks": 1, "attempts_allowed": 2,
        }).json()
        # Fail first
        requests.post(f"{API}/assessments/{a['id']}/submit", headers=_h,
                      json={"assessment_id": a["id"], "answers": [1]})
        # Pass second
        r = requests.post(f"{API}/assessments/{a['id']}/submit", headers=_h,
                         json={"assessment_id": a["id"], "answers": [0]})
        assert r.json()["result"]["passed"] is True
        # Now further submits should be allowed (no 429) — attempts bypassed
        r_more = requests.post(f"{API}/assessments/{a['id']}/submit", headers=_h,
                               json={"assessment_id": a["id"], "answers": [0]})
        assert r_more.status_code == 200

    def test_correct_index_stripped_and_meta_present(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               name_prefix="STRIP")
        m1 = _create_module(admin_h, prog["id"], 1)
        a = requests.post(f"{API}/assessments/admin", headers=admin_h, json={
            "module_id": m1["id"], "program_id": prog["id"], "title": "TEST_ST",
            "questions": [
                {"question": "q1", "options": ["a", "b"], "correct_index": 0},
                {"question": "q2", "options": ["x", "y"], "correct_index": 1},
                {"question": "q3", "options": ["p", "q"], "correct_index": 0},
            ],
            "passing_marks": 2, "attempts_allowed": 5, "randomize": True,
        }).json()
        r = requests.get(f"{API}/assessments/{a['id']}", headers=_h)
        assert r.status_code == 200
        d = r.json()
        assert "attempts_used" in d
        assert "can_attempt" in d
        assert d["attempts_used"] == 0
        assert d["can_attempt"] is True
        # correct_index MUST be stripped
        for q in d["questions"]:
            assert set(q.keys()) == {"question", "options"}, q
            assert "correct_index" not in q

    def test_randomize_deterministic_per_attempt(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               name_prefix="RND")
        m1 = _create_module(admin_h, prog["id"], 1)
        # 4 distinct questions to make ordering observable
        a = requests.post(f"{API}/assessments/admin", headers=admin_h, json={
            "module_id": m1["id"], "program_id": prog["id"], "title": "TEST_RND",
            "questions": [
                {"question": "Q_ALPHA", "options": ["a", "b"], "correct_index": 0},
                {"question": "Q_BETA", "options": ["a", "b"], "correct_index": 0},
                {"question": "Q_GAMMA", "options": ["a", "b"], "correct_index": 0},
                {"question": "Q_DELTA", "options": ["a", "b"], "correct_index": 0},
            ],
            "passing_marks": 4, "attempts_allowed": 5, "randomize": True,
        }).json()
        r1 = requests.get(f"{API}/assessments/{a['id']}", headers=_h).json()
        r2 = requests.get(f"{API}/assessments/{a['id']}", headers=_h).json()
        # Deterministic per (user, assessment, attempts_used): same on two GETs.
        seq1 = [q["question"] for q in r1["questions"]]
        seq2 = [q["question"] for q in r2["questions"]]
        assert seq1 == seq2, (seq1, seq2)


# ============ Content token / streaming =====================================
class TestContentToken:
    def test_token_and_stream_happy_path(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               name_prefix="CT")
        m1 = _create_module(admin_h, prog["id"], 1,
                           video_url="https://example.com/vid.mp4")
        requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                      json={"program_id": prog["id"]})

        r = requests.post(f"{API}/content/token", headers=_h, params={
            "program_id": prog["id"], "module_id": m1["id"], "resource": "video",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["stream_url"].startswith("/api/content/stream/")
        assert d["expires_in_seconds"] > 0
        assert "user_name" in d["watermark"]
        assert d["watermark"]["membership_id"] == _u["membership_id"]
        token = d["stream_url"].split("/")[-1]

        # GET stream — 302, no-store, inline
        r2 = requests.get(f"{API}/content/stream/{token}", allow_redirects=False)
        assert r2.status_code == 302, r2.text
        assert r2.headers.get("Location") == "https://example.com/vid.mp4"
        # Cache-Control may include additional directives (e.g. from a
        # global middleware); we only require `no-store` to be present.
        assert "no-store" in (r2.headers.get("Cache-Control") or "")
        assert r2.headers.get("Content-Disposition") == "inline"

    def test_no_resource_url_returns_404(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               name_prefix="CT404")
        m1 = _create_module(admin_h, prog["id"], 1)  # no video_url
        requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                      json={"program_id": prog["id"]})
        r = requests.post(f"{API}/content/token", headers=_h, params={
            "program_id": prog["id"], "module_id": m1["id"], "resource": "video",
        })
        assert r.status_code == 404

    def test_locked_module_returns_403(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               name_prefix="CTLOCK")
        _create_module(admin_h, prog["id"], 1, video_url="https://example.com/1.mp4")
        m2 = _create_module(admin_h, prog["id"], 2, video_url="https://example.com/2.mp4")
        requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                      json={"program_id": prog["id"]})
        r = requests.post(f"{API}/content/token", headers=_h, params={
            "program_id": prog["id"], "module_id": m2["id"], "resource": "video",
        })
        assert r.status_code == 403

    def test_invalid_token_returns_401(self):
        r = requests.get(f"{API}/content/stream/not.a.token", allow_redirects=False)
        assert r.status_code == 401

    def test_soft_delete_purchase_revokes_stream(self, admin_h, s, foundation_cat, mongo):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               name_prefix="CTREV")
        m1 = _create_module(admin_h, prog["id"], 1,
                           video_url="https://example.com/rev.mp4")
        pur_resp = requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                                 json={"program_id": prog["id"]})
        pur = pur_resp.json()

        r = requests.post(f"{API}/content/token", headers=_h, params={
            "program_id": prog["id"], "module_id": m1["id"], "resource": "video",
        })
        token = r.json()["stream_url"].split("/")[-1]
        # Works first
        r_ok = requests.get(f"{API}/content/stream/{token}", allow_redirects=False)
        assert r_ok.status_code == 302

        # Soft-delete purchase directly in Mongo (no API for user delete)
        from datetime import datetime, timezone
        mongo.program_purchases.update_one(
            {"id": pur["id"]},
            {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat()}},
        )
        r_rev = requests.get(f"{API}/content/stream/{token}", allow_redirects=False)
        assert r_rev.status_code == 403


# ============ Continue-learning + Dashboard =================================
class TestDashboardAndContinue:
    def test_continue_learning_and_dashboard(self, admin_h, s, foundation_cat):
        _u = _register_user(s)
        _h = {"Authorization": f"Bearer {_u['access']}", "Content-Type": "application/json"}

        # No purchases → continue-learning is None; dashboard has counts
        r0 = requests.get(f"{API}/programs/me/continue-learning", headers=_h)
        assert r0.status_code == 200
        assert r0.json() is None

        rd = requests.get(f"{API}/programs/me/dashboard", headers=_h)
        assert rd.status_code == 200
        for k in ("counts", "purchased", "completed", "expired", "locked", "available"):
            assert k in rd.json()

        # Now purchase + partially progress one program
        prog = _create_program(admin_h, foundation_cat["id"], is_subscription=True,
                               name_prefix="CL")
        m1 = _create_module(admin_h, prog["id"], 1)
        m2 = _create_module(admin_h, prog["id"], 2)
        requests.post(f"{API}/programs/{prog['id']}/purchase", headers=_h,
                      json={"program_id": prog["id"]})
        requests.post(f"{API}/progress/me/{prog['id']}/module/{m1['id']}/complete",
                      headers=_h, json={"time_spent_sec": 3})

        r = requests.get(f"{API}/programs/me/continue-learning", headers=_h)
        assert r.status_code == 200
        d = r.json()
        assert d is not None
        assert d["program"]["id"] == prog["id"]
        assert d["progress"]["program_id"] == prog["id"]

        # Dashboard: this prog should show in 'purchased' with validity_remaining_days.
        rd2 = requests.get(f"{API}/programs/me/dashboard", headers=_h)
        assert rd2.status_code == 200
        d2 = rd2.json()
        purchased_ids = [e["program"]["id"] for e in d2["purchased"]]
        assert prog["id"] in purchased_ids, d2
        entry = [e for e in d2["purchased"] if e["program"]["id"] == prog["id"]][0]
        assert entry["validity_remaining_days"] is not None
        assert entry["active_purchase"] is not None
        assert entry["progress"]["percentage"] == 50.0
