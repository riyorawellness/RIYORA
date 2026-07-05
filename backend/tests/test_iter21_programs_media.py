"""Iteration 21 — Admin Programs / Modules / Media Library backend tests.

Covers:
  * `get_current_user_or_admin` dep — admin token can now GET
    /api/programs, /api/programs/{id}, /api/modules, /api/modules/{id},
    /api/categories. Regression: regular user still works and does NOT see
    inactive programs (admin privilege).
  * Programs admin CRUD + slug uniqueness + activate/deactivate + soft-delete.
  * Modules admin CRUD + duplicate module_number → 409 + swap-reorder pattern.
  * File uploads: image / pdf / mp3 → 201 with `url`. GET /api/uploads/{id}
    serves file back. DELETE soft-deletes.
"""
from __future__ import annotations

import io
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://rw-subscription-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"

# ------------------ Fixtures ------------------

@pytest.fixture(scope="session")
def admin_token() -> str:
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = (data.get("tokens") or {}).get("access_token") or data.get("access_token")
    assert tok, f"no access_token in {data}"
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def user_token() -> str:
    """Register + login a throwaway user; dev OTP=123456 accepted."""
    mobile = f"9{int(time.time()) % 1000000000:09d}"
    # send OTP
    r = requests.post(f"{API}/auth/send-otp", json={"mobile": mobile, "purpose": "register"}, timeout=15)
    assert r.status_code == 200, r.text
    # verify OTP
    r = requests.post(
        f"{API}/auth/verify-otp",
        json={"mobile": mobile, "purpose": "register", "code": "123456"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    verification_token = r.json().get("verification_token") or r.json().get("token")
    payload = {
        "mobile": mobile,
        "full_name": "TEST_ITER21_USER",
        "state": "Karnataka",
        "city": "Bengaluru",
        "referral_id": "RW000000",
        "password": "Passw0rd!",
        "confirm_password": "Passw0rd!",
    }
    r = requests.post(f"{API}/auth/register", json=payload, timeout=15)
    assert r.status_code in (200, 201), f"register: {r.status_code} {r.text}"
    reg = r.json()
    tok = (reg.get("tokens") or {}).get("access_token") or reg.get("access_token")
    if not tok:
        r = requests.post(
            f"{API}/auth/login", json={"mobile": mobile, "password": "Passw0rd!"}, timeout=15
        )
        assert r.status_code == 200, r.text
        tok = r.json()["tokens"]["access_token"]
    return tok


@pytest.fixture(scope="session")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}


# ------------------ Track created ids for teardown ------------------
_created_programs: list[str] = []
_created_modules: list[str] = []
_created_uploads: list[str] = []


@pytest.fixture(scope="session", autouse=True)
def _teardown(admin_headers):
    yield
    for mid in _created_modules:
        try:
            requests.delete(f"{API}/modules/admin/{mid}", headers=admin_headers, timeout=10)
        except Exception:
            pass
    for pid in _created_programs:
        try:
            requests.delete(f"{API}/programs/admin/{pid}", headers=admin_headers, timeout=10)
        except Exception:
            pass
    for uid in _created_uploads:
        try:
            requests.delete(f"{API}/admin/uploads/{uid}", headers=admin_headers, timeout=10)
        except Exception:
            pass


# ================== 1. Dep test — admin can GET catalog endpoints ==================

class TestAdminReadCatalog:
    def test_admin_can_list_programs(self, admin_headers):
        r = requests.get(f"{API}/programs", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body and isinstance(body["items"], list)

    def test_admin_can_list_categories(self, admin_headers):
        r = requests.get(f"{API}/categories", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert "items" in r.json()

    def test_admin_can_list_modules(self, admin_headers):
        r = requests.get(f"{API}/modules", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert "items" in r.json()

    def test_user_can_list_programs(self, user_headers):
        r = requests.get(f"{API}/programs", headers=user_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert "items" in r.json()

    def test_user_does_not_see_inactive_programs(self, admin_headers, user_headers):
        """Regression: create inactive program as admin, user must not see it."""
        slug = f"iter21-inactive-{uuid.uuid4().hex[:8]}"
        payload = {
            "name": "TEST_ITER21 Inactive",
            "slug": slug,
            "price": 100,
            "validity_days": 30,
            "is_active": False,
        }
        r = requests.post(f"{API}/programs/admin", headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        _created_programs.append(pid)

        # admin sees it in list without is_active filter
        r = requests.get(f"{API}/programs?page_size=200", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert any(p["id"] == pid for p in r.json()["items"]), "admin should see inactive program"

        # user must NOT see it
        r = requests.get(f"{API}/programs?page_size=200", headers=user_headers, timeout=15)
        assert r.status_code == 200
        assert not any(p["id"] == pid for p in r.json()["items"]), "user must not see inactive program"

    def test_get_without_token_returns_401(self):
        r = requests.get(f"{API}/programs", timeout=15)
        assert r.status_code == 401, r.text


# ================== 2. Programs admin CRUD ==================

class TestProgramsCRUD:
    def test_create_program(self, admin_headers):
        slug = f"iter21-prog-{uuid.uuid4().hex[:8]}"
        r = requests.post(
            f"{API}/programs/admin",
            headers=admin_headers,
            json={
                "name": "TEST_ITER21 Program",
                "slug": slug,
                "price": 999.0,
                "validity_days": 90,
                "gst_percent": 18,
                "is_active": True,
            },
            timeout=15,
        )
        assert r.status_code == 201, r.text
        doc = r.json()
        assert doc["name"] == "TEST_ITER21 Program"
        assert doc["slug"] == slug
        assert doc["price"] == 999.0
        assert doc["validity_days"] == 90
        assert doc["is_active"] is True
        assert "id" in doc
        _created_programs.append(doc["id"])
        pytest.shared_program_id = doc["id"]
        pytest.shared_program_slug = slug

    def test_create_program_duplicate_slug_returns_409(self, admin_headers):
        slug = getattr(pytest, "shared_program_slug", None)
        assert slug, "prior create must have run"
        r = requests.post(
            f"{API}/programs/admin",
            headers=admin_headers,
            json={"name": "dup", "slug": slug, "price": 1, "validity_days": 1},
            timeout=15,
        )
        assert r.status_code == 409, r.text

    def test_get_program_by_id_as_admin(self, admin_headers):
        pid = pytest.shared_program_id
        r = requests.get(f"{API}/programs/{pid}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["id"] == pid

    def test_update_program_and_persist(self, admin_headers):
        pid = pytest.shared_program_id
        r = requests.put(
            f"{API}/programs/admin/{pid}",
            headers=admin_headers,
            json={"price": 1499.0, "short_description": "updated"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["price"] == 1499.0
        # verify persistence
        r = requests.get(f"{API}/programs/{pid}", headers=admin_headers, timeout=15)
        assert r.json()["price"] == 1499.0
        assert r.json()["short_description"] == "updated"

    def test_deactivate_and_activate(self, admin_headers):
        pid = pytest.shared_program_id
        r = requests.post(f"{API}/programs/admin/{pid}/deactivate", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["is_active"] is False
        r = requests.post(f"{API}/programs/admin/{pid}/activate", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["is_active"] is True

    def test_soft_delete_program(self, admin_headers):
        slug = f"iter21-del-{uuid.uuid4().hex[:8]}"
        r = requests.post(
            f"{API}/programs/admin",
            headers=admin_headers,
            json={"name": "TEST_ITER21 delete", "slug": slug, "price": 1, "validity_days": 1},
            timeout=15,
        )
        pid = r.json()["id"]
        r = requests.delete(f"{API}/programs/admin/{pid}", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        # 404 after soft-delete
        r = requests.get(f"{API}/programs/{pid}", headers=admin_headers, timeout=15)
        assert r.status_code == 404


# ================== 3. Modules admin CRUD ==================

class TestModulesCRUD:
    def test_create_module(self, admin_headers):
        pid = pytest.shared_program_id
        r = requests.post(
            f"{API}/modules/admin",
            headers=admin_headers,
            json={
                "program_id": pid,
                "module_number": 1,
                "name": "TEST_ITER21 mod 1",
                "description": "first",
            },
            timeout=15,
        )
        assert r.status_code == 201, r.text
        m1 = r.json()
        assert m1["module_number"] == 1
        _created_modules.append(m1["id"])
        pytest.shared_module_1 = m1["id"]

        # module 2
        r = requests.post(
            f"{API}/modules/admin",
            headers=admin_headers,
            json={"program_id": pid, "module_number": 2, "name": "TEST_ITER21 mod 2"},
            timeout=15,
        )
        assert r.status_code == 201, r.text
        _created_modules.append(r.json()["id"])
        pytest.shared_module_2 = r.json()["id"]

    def test_duplicate_module_number_returns_409(self, admin_headers):
        pid = pytest.shared_program_id
        r = requests.post(
            f"{API}/modules/admin",
            headers=admin_headers,
            json={"program_id": pid, "module_number": 1, "name": "dup"},
            timeout=15,
        )
        assert r.status_code == 409, r.text

    def test_list_modules_by_program(self, admin_headers):
        pid = pytest.shared_program_id
        r = requests.get(f"{API}/modules?program_id={pid}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        nums = sorted(m["module_number"] for m in r.json()["items"])
        assert nums == [1, 2]

    def test_swap_reorder_pattern(self, admin_headers):
        """Emulate FE reorder: bump m1 to a temp number, then swap m2→1, m1→2."""
        m1 = pytest.shared_module_1
        m2 = pytest.shared_module_2
        # step 1: park m1 at 999
        r = requests.put(f"{API}/modules/admin/{m1}", headers=admin_headers, json={"module_number": 999}, timeout=15)
        assert r.status_code == 200, r.text
        # step 2: move m2 to 1
        r = requests.put(f"{API}/modules/admin/{m2}", headers=admin_headers, json={"module_number": 1}, timeout=15)
        assert r.status_code == 200, r.text
        # step 3: move m1 to 2
        r = requests.put(f"{API}/modules/admin/{m1}", headers=admin_headers, json={"module_number": 2}, timeout=15)
        assert r.status_code == 200, r.text

        # verify order swapped
        pid = pytest.shared_program_id
        r = requests.get(f"{API}/modules?program_id={pid}", headers=admin_headers, timeout=15)
        items = sorted(r.json()["items"], key=lambda x: x["module_number"])
        assert items[0]["id"] == m2 and items[0]["module_number"] == 1
        assert items[1]["id"] == m1 and items[1]["module_number"] == 2

    def test_delete_module(self, admin_headers):
        pid = pytest.shared_program_id
        # create a throwaway module 3
        r = requests.post(
            f"{API}/modules/admin",
            headers=admin_headers,
            json={"program_id": pid, "module_number": 3, "name": "TEST_ITER21 mod 3"},
            timeout=15,
        )
        mid = r.json()["id"]
        r = requests.delete(f"{API}/modules/admin/{mid}", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        r = requests.get(f"{API}/modules/{mid}", headers=admin_headers, timeout=15)
        assert r.status_code == 404


# ================== 4. Uploads ==================

def _upload(admin_token: str, filename: str, content: bytes, content_type: str):
    r = requests.post(
        f"{API}/admin/uploads",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": (filename, content, content_type)},
        timeout=30,
    )
    return r


# tiny 1x1 PNG (67 bytes)
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049"
    "454e44ae426082"
)

# minimal PDF (~200 bytes)
_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
    b"0000000053 00000 n\n0000000098 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n148\n%%EOF"
)

# minimal MP3 (silent frame header)
_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 200


class TestUploads:
    def test_upload_png(self, admin_token):
        r = _upload(admin_token, "iter21.png", _PNG, "image/png")
        assert r.status_code == 201, r.text
        doc = r.json()
        assert "url" in doc and doc["url"].startswith("/api/uploads/")
        assert doc["content_type"] == "image/png"
        assert doc["size_bytes"] == len(_PNG)
        _created_uploads.append(doc["id"])
        pytest.shared_png = doc

    def test_upload_pdf(self, admin_token):
        r = _upload(admin_token, "iter21.pdf", _PDF, "application/pdf")
        assert r.status_code == 201, r.text
        doc = r.json()
        assert doc["content_type"] == "application/pdf"
        _created_uploads.append(doc["id"])

    def test_upload_mp3(self, admin_token):
        r = _upload(admin_token, "iter21.mp3", _MP3, "audio/mpeg")
        assert r.status_code == 201, r.text
        doc = r.json()
        assert doc["content_type"].startswith("audio/")
        _created_uploads.append(doc["id"])

    def test_get_upload_serves_file(self, admin_token):
        doc = pytest.shared_png
        # public GET (no auth)
        r = requests.get(f"{BASE_URL}{doc['url']}", timeout=15)
        assert r.status_code == 200, r.text
        assert r.content == _PNG
        assert r.headers.get("content-type", "").startswith("image/png")

    def test_delete_upload(self, admin_token):
        # upload a throwaway
        r = _upload(admin_token, "iter21-del.png", _PNG, "image/png")
        uid = r.json()["id"]
        url = r.json()["url"]
        r = requests.delete(
            f"{API}/admin/uploads/{uid}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        # after delete GET returns 404
        r = requests.get(f"{BASE_URL}{url}", timeout=15)
        assert r.status_code == 404

    def test_list_uploads(self, admin_headers):
        r = requests.get(f"{API}/admin/uploads?page_size=200", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()["items"]]
        # first PNG we uploaded must be present
        assert pytest.shared_png["id"] in ids

    def test_upload_unauthorized(self):
        r = requests.post(
            f"{API}/admin/uploads",
            files={"file": ("x.png", _PNG, "image/png")},
            timeout=15,
        )
        assert r.status_code == 401
