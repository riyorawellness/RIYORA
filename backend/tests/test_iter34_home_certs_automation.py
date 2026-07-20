"""iter34 — Backend coverage for the 4 UX changes:
  1) Home banner endpoint (`/api/banners/active?placement=home`)
  2) Featured programs filter (`/api/programs?is_featured=true`)
  3) Auto-cert issuance + auto-log-session on final module completion
     via POST /api/progress/me/{program_id}/module/{module_id}/complete
  4) Idempotency of certificate issuance on repeat calls
  5) Certificate list & detail endpoints for the user
"""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# --------------------------- fixtures -------------------------------------


@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL)
    db_name = DB_NAME
    # Discover db name if not set — server.py uses same var
    return client[db_name]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": "9999999999", "password": "Admin@12345"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": "qa-tester@example.com", "password": "tester123"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    tok = body.get("tokens", {}).get("access_token") or body.get("access_token")
    assert tok, f"No access token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tester_membership_id(user_headers):
    r = requests.get(f"{API}/auth/me", headers=user_headers, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["membership_id"]


# --------------------------- 1. banners ------------------------------------


class TestHomeBanner:
    """Verify /api/banners/active?placement=home works. Create a test banner
    if none exist so the frontend has something to render."""

    def test_banners_endpoint_reachable(self, admin_headers):
        r = requests.get(f"{API}/banners/active", params={"placement": "home"}, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_seed_home_banner_if_absent(self, admin_headers):
        r = requests.get(f"{API}/banners/active", params={"placement": "home"}, timeout=10)
        items = r.json().get("items", [])
        if items:
            return  # already have one
        payload = {
            "title": f"TEST_iter34_banner_{uuid.uuid4().hex[:6]}",
            "image_url": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=1400",
            "cta_label": "Learn more",
            "cta_link": "/app/programs",
            "placement": "home",
            "priority": 100,
            "is_active": True,
        }
        r2 = requests.post(
            f"{API}/admin/banners", json=payload, headers=admin_headers, timeout=15
        )
        assert r2.status_code == 201, r2.text
        # confirm now visible
        r3 = requests.get(f"{API}/banners/active", params={"placement": "home"}, timeout=10)
        assert r3.status_code == 200
        titles = [b["title"] for b in r3.json().get("items", [])]
        assert payload["title"] in titles


# --------------------------- 2. featured programs -------------------------


class TestFeaturedPrograms:
    """Ensure at least 2 programs are marked is_featured and confirm the
    filter returns only featured programs."""

    def _list_programs(self, params=None, headers=None):
        return requests.get(f"{API}/programs", params=params or {}, headers=headers or {}, timeout=15)

    def test_featured_filter_returns_only_featured(self, admin_headers, user_headers):
        # First list currently featured
        r = self._list_programs({"is_featured": True, "page_size": 50}, headers=user_headers)
        assert r.status_code == 200, r.text
        featured = r.json().get("items", [])
        # Ensure we have >=2 featured programs — flag more if needed.
        if len(featured) < 2:
            # Fetch some inactive-featured programs and mark them featured
            r_all = self._list_programs({"is_active": True, "page_size": 20}, headers=user_headers)
            assert r_all.status_code == 200
            all_prog = r_all.json().get("items", [])
            need = 2 - len(featured)
            flagged_ids = []
            for p in all_prog:
                if p.get("is_featured"):
                    continue
                pr = requests.put(
                    f"{API}/programs/admin/{p['id']}",
                    json={"is_featured": True},
                    headers=admin_headers,
                    timeout=15,
                )
                assert pr.status_code == 200, pr.text
                flagged_ids.append(p["id"])
                if len(flagged_ids) >= need:
                    break
            r2 = self._list_programs({"is_featured": True, "page_size": 50}, headers=user_headers)
            featured = r2.json().get("items", [])
        assert len(featured) >= 2, f"Only {len(featured)} featured programs"
        # All returned MUST be is_featured=True
        for p in featured:
            assert p.get("is_featured") is True, p

    def test_non_featured_excluded_from_featured_filter(self, user_headers):
        r_featured = self._list_programs({"is_featured": True, "page_size": 100}, headers=user_headers)
        r_not = self._list_programs({"is_featured": False, "page_size": 100}, headers=user_headers)
        assert r_featured.status_code == 200 and r_not.status_code == 200
        feat_ids = {p["id"] for p in r_featured.json().get("items", [])}
        nonfeat_ids = {p["id"] for p in r_not.json().get("items", [])}
        # No overlap
        assert not (feat_ids & nonfeat_ids), "Overlap between featured & not"


# --------------------------- 3+4. auto certificate + idempotency + session log


class TestAutoCertificateOnFinalModule:
    """The most critical review requirement.

    Seed a small program (2 modules, no assessment), give qa-tester an active
    purchase, complete the 2 modules — the LAST call should:
      * return {progress, certificate}
      * certificate has status=issued, cert #, verification #, program_name, completion_date
      * an activity_sessions row is written with source='module_complete' + the module_id
      * a second call is idempotent — same cert id + number.
    """

    prog_id = None
    module_ids = []

    def test_seed_program_and_purchase(self, admin_headers, user_headers, mongo_db, tester_membership_id):
        # 1) Create a fresh category
        cat_slug = f"test-iter34-cat-{uuid.uuid4().hex[:6]}"
        r_cat = requests.post(
            f"{API}/categories/admin",
            json={"name": cat_slug, "slug": cat_slug, "order_index": 99},
            headers=admin_headers,
            timeout=15,
        )
        assert r_cat.status_code in (200, 201), r_cat.text
        cat = r_cat.json()
        cat_id = cat["id"]

        # 2) Create a fresh program (one-time, cheap price, access_mode=free so no sequential gate issues)
        prog_slug = f"test-iter34-prog-{uuid.uuid4().hex[:6]}"
        r_prog = requests.post(
            f"{API}/programs/admin",
            json={
                "name": prog_slug,
                "slug": prog_slug,
                "category_id": cat_id,
                "price": 100,
                "validity_days": 365,
                "is_active": True,
                "access_mode": "free",
                "is_featured": False,
            },
            headers=admin_headers,
            timeout=15,
        )
        assert r_prog.status_code in (200, 201), r_prog.text
        prog = r_prog.json()
        TestAutoCertificateOnFinalModule.prog_id = prog["id"]

        # 3) Create 2 modules
        module_ids = []
        for i in (1, 2):
            r_m = requests.post(
                f"{API}/modules/admin",
                json={
                    "program_id": prog["id"],
                    "name": f"TEST_iter34_mod_{i}",
                    "module_number": i,
                    "type": "video",
                    "video_url": "https://example.com/v.mp4",
                    "duration_minutes": 5,
                    "sequential_unlock": False,
                },
                headers=admin_headers,
                timeout=15,
            )
            assert r_m.status_code in (200, 201), r_m.text
            module_ids.append(r_m.json()["id"])
        TestAutoCertificateOnFinalModule.module_ids = module_ids

        # 4) Directly insert an active purchase for tester (bypass razorpay)
        # Use the collection directly.
        now_iso = "2026-01-01T00:00:00+00:00"
        purchase_doc = {
            "id": str(uuid.uuid4()),
            "user_membership_id": tester_membership_id,
            "program_id": prog["id"],
            "program_name": prog_slug,
            "amount": 100,
            "total": 100,
            "status": "active",
            "payment_status": "success",
            "purchase_date": now_iso,
            "expiry_date": "2099-12-31T23:59:59+00:00",
            "created_at": now_iso,
            "updated_at": now_iso,
            "deleted_at": None,
            "is_dummy": True,
            "razorpay_payment_id": f"pay_test_iter34_{uuid.uuid4().hex[:8]}",
            "razorpay_order_id": f"order_test_iter34_{uuid.uuid4().hex[:8]}",
            "invoice_number": f"INV-TEST-{uuid.uuid4().hex[:12].upper()}",
        }
        mongo_db.program_purchases.insert_one(purchase_doc)

        # sanity — user can see they have an active purchase
        r_mine = requests.get(f"{API}/purchases/me", headers=user_headers, timeout=10)
        assert r_mine.status_code == 200, r_mine.text

    def test_complete_first_module_no_cert(self, user_headers):
        assert self.prog_id and self.module_ids, "Setup did not run"
        m1 = self.module_ids[0]
        r = requests.post(
            f"{API}/progress/me/{self.prog_id}/module/{m1}/complete",
            json={"time_spent_sec": 30},
            headers=user_headers,
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "progress" in body and "certificate" in body
        # After completing 1/2, cert should NOT yet be issued
        assert body["certificate"] is None
        # percentage should be ~50
        assert 40 <= body["progress"].get("percentage", 0) <= 60

    def test_complete_final_module_issues_cert_and_logs_session(
        self, user_headers, mongo_db, tester_membership_id
    ):
        m2 = self.module_ids[1]
        r = requests.post(
            f"{API}/progress/me/{self.prog_id}/module/{m2}/complete",
            json={"time_spent_sec": 42},
            headers=user_headers,
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "progress" in body and "certificate" in body
        cert = body["certificate"]
        assert cert is not None, f"Expected cert on final module — got {body}"
        # Required fields
        for f in ("id", "program_name", "certificate_number", "verification_number", "completion_date", "status"):
            assert f in cert, f"Certificate missing field {f}: {cert}"
        assert cert["status"] == "issued"
        assert cert["program_name"]
        # Percentage should be 100
        assert body["progress"].get("percentage", 0) >= 99

        # Save for idempotency test
        TestAutoCertificateOnFinalModule._cert_id = cert["id"]
        TestAutoCertificateOnFinalModule._cert_number = cert["certificate_number"]

        # Verify a session was auto-logged with source='module_complete' + module_id
        # Small sleep in case of any async lag (not strictly needed since log_session awaits)
        time.sleep(0.5)
        session = mongo_db.activity_sessions.find_one({
            "user_membership_id": tester_membership_id,
            "module_id": m2,
            "source": "module_complete",
        })
        assert session is not None, (
            "Expected activity_sessions row for module_complete with the just-completed module_id"
        )

    def test_complete_final_module_is_idempotent(self, user_headers):
        m2 = self.module_ids[1]
        r = requests.post(
            f"{API}/progress/me/{self.prog_id}/module/{m2}/complete",
            json={"time_spent_sec": 10},
            headers=user_headers,
            timeout=20,
        )
        assert r.status_code == 200, r.text
        cert = r.json().get("certificate")
        assert cert is not None
        assert cert["id"] == self._cert_id
        assert cert["certificate_number"] == self._cert_number


# --------------------------- 5. certificates endpoints ---------------------


class TestCertificatesMyEndpoints:
    def test_list_my_certificates(self, user_headers):
        r = requests.get(
            f"{API}/certificates/me",
            params={"page": 1, "page_size": 50, "sort": "-issue_date"},
            headers=user_headers,
            timeout=10,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        # After the auto-cert test, at least one cert should exist for tester
        assert len(data["items"]) >= 1
        for c in data["items"]:
            assert c["status"] == "issued"
            for f in ("id", "program_name", "certificate_number", "issue_date"):
                assert f in c, f"cert missing {f}"

    def test_get_my_certificate_detail(self, user_headers):
        # Grab first cert
        r = requests.get(
            f"{API}/certificates/me",
            params={"page": 1, "page_size": 1},
            headers=user_headers,
            timeout=10,
        )
        items = r.json().get("items", [])
        assert items, "No certs to test detail on"
        cid = items[0]["id"]
        r2 = requests.get(f"{API}/certificates/me/{cid}", headers=user_headers, timeout=10)
        assert r2.status_code == 200, r2.text
        c = r2.json()
        assert c["id"] == cid
        for f in ("program_name", "certificate_number", "verification_number", "completion_date", "user_membership_id"):
            assert f in c, f"detail missing {f}"

    def test_get_someone_elses_cert_404(self, user_headers):
        r = requests.get(
            f"{API}/certificates/me/{uuid.uuid4().hex}",
            headers=user_headers,
            timeout=10,
        )
        assert r.status_code == 404
