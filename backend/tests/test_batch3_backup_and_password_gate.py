"""Batch 3 — Danger Zone password gate + Backup/Restore regression."""
import os
import uuid
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


@pytest.fixture(scope="module")
def admin_h():
    r = requests.post(
        f"{API}/admin/login", json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD}
    )
    return {
        "Authorization": f"Bearer {r.json()['tokens']['access_token']}",
        "Content-Type": "application/json",
    }


class TestBackupsCRUD:
    def test_list_endpoint(self, admin_h):
        r = requests.get(f"{API}/admin/backups", headers=admin_h)
        assert r.status_code == 200
        assert "items" in r.json()

    def test_create_requires_password(self, admin_h):
        r = requests.post(
            f"{API}/admin/backups/create",
            headers=admin_h,
            json={"admin_password": ""},
        )
        assert r.status_code in (400, 403, 422)

    def test_create_wrong_password(self, admin_h):
        r = requests.post(
            f"{API}/admin/backups/create",
            headers=admin_h,
            json={"admin_password": "WrongPass!", "reason": "test"},
        )
        assert r.status_code == 403

    def test_create_and_delete_backup(self, admin_h):
        r = requests.post(
            f"{API}/admin/backups/create",
            headers=admin_h,
            json={"admin_password": ADMIN_PASSWORD, "reason": f"pytest_{uuid.uuid4().hex[:6]}"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["success"] is True
        fname = d["backup"]["filename"]
        assert d["backup"]["size_bytes"] > 0

        # Confirm it appears in list
        listing = requests.get(f"{API}/admin/backups", headers=admin_h).json()
        assert any(x["filename"] == fname for x in listing["items"])

        # Delete
        rd = requests.request(
            "DELETE",
            f"{API}/admin/backups/{fname}",
            headers=admin_h,
            json={"admin_password": ADMIN_PASSWORD},
        )
        assert rd.status_code == 200

    def test_delete_wrong_password(self, admin_h):
        # Create then attempt delete with wrong pw
        r = requests.post(
            f"{API}/admin/backups/create",
            headers=admin_h,
            json={"admin_password": ADMIN_PASSWORD, "reason": "for_delete_test"},
        )
        fname = r.json()["backup"]["filename"]
        rd = requests.request(
            "DELETE",
            f"{API}/admin/backups/{fname}",
            headers=admin_h,
            json={"admin_password": "NotThePassword"},
        )
        assert rd.status_code == 403
        # Cleanup
        requests.request(
            "DELETE",
            f"{API}/admin/backups/{fname}",
            headers=admin_h,
            json={"admin_password": ADMIN_PASSWORD},
        )

    def test_path_traversal_rejected(self, admin_h):
        r = requests.post(
            f"{API}/admin/backups/..%2Fetc%2Fpasswd/restore",
            headers=admin_h,
            json={"admin_password": ADMIN_PASSWORD},
        )
        # Rejected either by FastAPI route matching or by our validator
        assert r.status_code in (400, 404, 422)


class TestDangerZonePasswordGate:
    def test_empty_app_data_requires_password_field(self, admin_h):
        r = requests.post(
            f"{API}/admin/danger/empty-app-data",
            headers=admin_h,
            json={"confirmation": "EMPTY APP DATA"},
        )
        assert r.status_code == 422  # missing required admin_password

    def test_empty_app_data_wrong_password(self, admin_h):
        r = requests.post(
            f"{API}/admin/danger/empty-app-data",
            headers=admin_h,
            json={"confirmation": "EMPTY APP DATA", "admin_password": "wrong"},
        )
        assert r.status_code == 403

    def test_empty_app_data_wrong_confirmation(self, admin_h):
        r = requests.post(
            f"{API}/admin/danger/empty-app-data",
            headers=admin_h,
            json={"confirmation": "delete everything", "admin_password": ADMIN_PASSWORD},
        )
        assert r.status_code == 400
