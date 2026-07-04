"""Phase 11 — Manual QR Payment System backend tests."""
from __future__ import annotations

import io
import os
import struct
import time
import zlib
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_MOBILE = "9999999999"
ADMIN_PASSWORD = "Admin@12345"
USER_MOBILE = "7802655202"
USER_PASSWORD = "Passw0rd!"


# ---------- helpers -------------------------------------------------------


def _tiny_png_bytes() -> bytes:
    """Return a valid 1x1 PNG (magic bytes must pass file_validator)."""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = b"\x00\xff\xff\xff"  # filter + 1 white pixel RGB
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


PNG_BYTES = _tiny_png_bytes()


# ---------- fixtures ------------------------------------------------------


@pytest.fixture(scope="session")
def admin_token() -> str:
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": ADMIN_MOBILE, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="session")
def user_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"mobile": USER_MOBILE, "password": USER_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"User login failed: {r.status_code} {r.text}")
    return r.json()["tokens"]["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="session")
def onetime_programs(user_headers) -> list[dict]:
    """List of programs where is_subscription != True."""
    r = requests.get(f"{API}/programs?page=1&page_size=100", headers=user_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data.get("items") or data.get("programs") or data
    if isinstance(items, dict) and "items" in items:
        items = items["items"]
    return [p for p in items if not p.get("is_subscription")]


@pytest.fixture(scope="session")
def subscription_program(user_headers) -> dict | None:
    r = requests.get(f"{API}/programs?page=1&page_size=100", headers=user_headers, timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    items = data.get("items") or data.get("programs") or data
    if isinstance(items, dict) and "items" in items:
        items = items["items"]
    subs = [p for p in items if p.get("is_subscription")]
    return subs[0] if subs else None


# ---------- payment mode / public settings --------------------------------


class TestPaymentMode:
    def test_get_payment_mode_no_auth(self):
        r = requests.get(f"{API}/payments/mode", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["payment_mode"] in ("manual_qr", "razorpay", "both")

    def test_admin_get_settings(self, admin_headers):
        r = requests.get(f"{API}/admin/payments/settings", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "payment_mode" in body
        assert "active_qr" in body
        qr = body["active_qr"] or {}
        # Seeded per review request context
        assert qr.get("company_name") == "RIYORA Wellness Pvt Ltd", qr
        assert qr.get("upi_id") == "riyorawellness@hdfc", qr

    def test_admin_put_settings_persists(self, admin_headers):
        # Round-trip: change payment_instructions then revert.
        original = requests.get(f"{API}/admin/payments/settings", headers=admin_headers, timeout=20).json()
        orig_instr = (original.get("active_qr") or {}).get("payment_instructions")
        new_instr = f"TEST_phase11_{int(time.time())}"
        r = requests.put(
            f"{API}/admin/payments/settings",
            json={"payment_instructions": new_instr},
            headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        fresh = requests.get(f"{API}/admin/payments/settings", headers=admin_headers, timeout=20).json()
        assert fresh["active_qr"]["payment_instructions"] == new_instr
        # revert
        requests.put(
            f"{API}/admin/payments/settings",
            json={"payment_instructions": orig_instr},
            headers=admin_headers, timeout=20,
        )

    def test_admin_toggle_payment_mode(self, admin_headers):
        r1 = requests.put(f"{API}/admin/payments/mode", json={"payment_mode": "razorpay"},
                          headers=admin_headers, timeout=20)
        assert r1.status_code == 200
        g1 = requests.get(f"{API}/payments/mode", timeout=20).json()
        assert g1["payment_mode"] == "razorpay"
        # revert to manual_qr
        r2 = requests.put(f"{API}/admin/payments/mode", json={"payment_mode": "manual_qr"},
                          headers=admin_headers, timeout=20)
        assert r2.status_code == 200
        g2 = requests.get(f"{API}/payments/mode", timeout=20).json()
        assert g2["payment_mode"] == "manual_qr"


# ---------- QR upload / serving ------------------------------------------


class TestQRUploadServe:
    def test_qr_upload_and_serve(self, admin_headers):
        # Upload QR
        r = requests.post(
            f"{API}/admin/payments/qr",
            headers=admin_headers,
            files={"file": ("qr.png", PNG_BYTES, "image/png")},
            timeout=30,
        )
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body["url"].startswith("/api/uploads/screenshot/qr-")
        url_path = body["url"]

        # Ensure settings reflects url
        settings = requests.get(f"{API}/admin/payments/settings", headers=admin_headers, timeout=20).json()
        assert settings["active_qr"]["qr_image_url"] == url_path

        # Serve — no auth required
        rr = requests.get(f"{BASE_URL}{url_path}", timeout=20)
        assert rr.status_code == 200
        assert rr.headers.get("content-type", "").startswith("image/") or len(rr.content) > 0

    def test_delete_qr_then_reupload(self, admin_headers):
        # Delete
        r = requests.delete(f"{API}/admin/payments/qr", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        s = requests.get(f"{API}/admin/payments/settings", headers=admin_headers, timeout=20).json()
        assert s["active_qr"]["qr_image_url"] is None

        # Reupload so downstream user tests can see QR
        rr = requests.post(
            f"{API}/admin/payments/qr", headers=admin_headers,
            files={"file": ("qr.png", PNG_BYTES, "image/png")}, timeout=30,
        )
        assert rr.status_code in (200, 201)


# ---------- User quote / submit flow -------------------------------------


class TestUserQuoteAndSubmit:
    def test_public_qr_requires_user(self, user_headers):
        r = requests.get(f"{API}/payments/manual/qr", headers=user_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("qr_image_url")
        assert body.get("company_name") == "RIYORA Wellness Pvt Ltd"
        assert body.get("upi_id") == "riyorawellness@hdfc"

    def test_quote_for_one_time_program(self, user_headers, onetime_programs):
        assert onetime_programs, "No one-time programs available"
        prog = onetime_programs[0]
        r = requests.get(
            f"{API}/payments/manual/quote?program_id={prog['id']}",
            headers=user_headers, timeout=20,
        )
        # Skip if user already has active or pending
        if r.status_code == 409:
            pytest.skip(f"user already has access/pending: {r.text}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["program"]["id"] == prog["id"]
        b = body["breakdown"]
        for k in ("price", "discount", "gst_percent", "gst_amount", "taxable", "total"):
            assert k in b, f"missing {k}"

    def test_quote_subscription_409(self, user_headers, subscription_program):
        if not subscription_program:
            pytest.skip("no subscription program available")
        r = requests.get(
            f"{API}/payments/manual/quote?program_id={subscription_program['id']}",
            headers=user_headers, timeout=20,
        )
        assert r.status_code == 409, r.text
        detail = r.json().get("detail", "").lower()
        assert "coming soon" in detail or "subscription" in detail

    def test_upload_screenshot(self, user_headers):
        r = requests.post(
            f"{API}/payments/manual/upload-screenshot",
            headers=user_headers,
            files={"file": ("s.png", PNG_BYTES, "image/png")},
            timeout=30,
        )
        assert r.status_code in (200, 201), r.text
        body = r.json()
        assert body["url"].startswith("/api/uploads/screenshot/ss-")

    @staticmethod
    def _pick_available_program(user_headers, onetime_programs) -> dict | None:
        """Find a one-time program where /quote returns 200 (no active/pending)."""
        for p in onetime_programs:
            r = requests.get(f"{API}/payments/manual/quote?program_id={p['id']}",
                             headers=user_headers, timeout=20)
            if r.status_code == 200:
                return p
        return None

    def test_submit_duplicate_and_history(self, user_headers, onetime_programs):
        prog = self._pick_available_program(user_headers, onetime_programs)
        if not prog:
            pytest.skip("no available one-time program for this user")

        up = requests.post(
            f"{API}/payments/manual/upload-screenshot",
            headers=user_headers,
            files={"file": ("s.png", PNG_BYTES, "image/png")},
            timeout=30,
        )
        assert up.status_code in (200, 201)
        ss_url = up.json()["url"]

        payload = {
            "program_id": prog["id"],
            "utr": f"UTRTEST{int(time.time())}",
            "transaction_date": datetime.now(timezone.utc).date().isoformat(),
            "screenshot_url": ss_url,
        }
        r = requests.post(f"{API}/payments/manual/submit", json=payload,
                          headers=user_headers, timeout=30)
        assert r.status_code == 201, r.text
        req = r.json()
        assert req["status"] == "pending"
        assert req["program_id"] == prog["id"]
        pytest.shared_pending_request_id = req["id"]
        pytest.shared_pending_program_id = prog["id"]

        # Duplicate submit → 409
        r2 = requests.post(f"{API}/payments/manual/submit", json=payload,
                           headers=user_headers, timeout=30)
        assert r2.status_code == 409, r2.text
        assert "pending" in r2.json().get("detail", "").lower()

        # Pending list
        p = requests.get(f"{API}/payments/manual/pending", headers=user_headers, timeout=20).json()
        assert any(x["id"] == req["id"] for x in p["items"])

        # History paginated
        h = requests.get(f"{API}/payments/manual/me?page_size=10", headers=user_headers, timeout=20).json()
        assert any(x["id"] == req["id"] for x in h["items"])
        assert h["page_size"] == 10

    def test_submit_subscription_409(self, user_headers, subscription_program):
        if not subscription_program:
            pytest.skip("no subscription program")
        payload = {
            "program_id": subscription_program["id"],
            "utr": "UTRTEST999999",
            "transaction_date": datetime.now(timezone.utc).date().isoformat(),
            "screenshot_url": "/api/uploads/screenshot/ss-fake.png",
        }
        r = requests.post(f"{API}/payments/manual/submit", json=payload,
                          headers=user_headers, timeout=20)
        assert r.status_code == 409, r.text


# ---------- Admin review ---------------------------------------------------


class TestAdminReview:
    def test_admin_summary(self, admin_headers):
        r = requests.get(f"{API}/admin/payments/manual/summary", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        for k in ("pending", "approved", "rejected"):
            assert k in body
            assert "count" in body[k]
            assert "amount" in body[k]
        assert body["pending"]["count"] >= 1

    def test_admin_list_pending(self, admin_headers):
        r = requests.get(f"{API}/admin/payments/manual?status=pending",
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        req_id = getattr(pytest, "shared_pending_request_id", None)
        if req_id:
            assert any(x["id"] == req_id for x in body["items"])

    def test_approve_and_verify_purchase(self, admin_headers, user_headers):
        req_id = getattr(pytest, "shared_pending_request_id", None)
        prog_id = getattr(pytest, "shared_pending_program_id", None)
        if not req_id:
            pytest.skip("no pending request from previous step")

        r = requests.post(
            f"{API}/admin/payments/manual/{req_id}/action",
            json={"action": "approve", "remarks": "verified"},
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True
        assert body.get("status") == "approved"
        assert body.get("purchase_id")

        # Re-approve → 409
        r2 = requests.post(
            f"{API}/admin/payments/manual/{req_id}/action",
            json={"action": "approve"},
            headers=admin_headers, timeout=20,
        )
        assert r2.status_code == 409, r2.text

        # Quote for same program → 409 already have access
        q = requests.get(f"{API}/payments/manual/quote?program_id={prog_id}",
                         headers=user_headers, timeout=20)
        assert q.status_code == 409, q.text
        assert "active access" in q.json().get("detail", "").lower()

        # Notification created — check /api/notifications
        n = requests.get(f"{API}/notifications?page_size=10", headers=user_headers, timeout=20)
        if n.status_code == 200:
            items = n.json().get("items", n.json())
            if isinstance(items, list):
                found = any(
                    (i.get("category") == "payment") and ("approv" in (i.get("title") or "").lower())
                    for i in items
                )
                assert found, f"No approved notification found: {items[:3]}"


# ---------- Rejection flow -----------------------------------------------


class TestRejectionFlow:
    def test_reject_then_resubmit(self, admin_headers, user_headers, onetime_programs):
        # Pick a different one-time program user can quote for.
        approved_prog_id = getattr(pytest, "shared_pending_program_id", None)
        target = None
        for p in onetime_programs:
            if p["id"] == approved_prog_id:
                continue
            q = requests.get(f"{API}/payments/manual/quote?program_id={p['id']}",
                             headers=user_headers, timeout=20)
            if q.status_code == 200:
                target = p
                break
        if not target:
            pytest.skip("no additional one-time program available for reject flow")

        up = requests.post(
            f"{API}/payments/manual/upload-screenshot",
            headers=user_headers,
            files={"file": ("s.png", PNG_BYTES, "image/png")},
            timeout=30,
        )
        ss_url = up.json()["url"]

        submit_body = {
            "program_id": target["id"],
            "utr": f"UTRREJ{int(time.time())}",
            "transaction_date": datetime.now(timezone.utc).date().isoformat(),
            "screenshot_url": ss_url,
        }
        r = requests.post(f"{API}/payments/manual/submit", json=submit_body,
                          headers=user_headers, timeout=30)
        assert r.status_code == 201, r.text
        req_id = r.json()["id"]

        # Reject
        rej = requests.post(
            f"{API}/admin/payments/manual/{req_id}/action",
            json={"action": "reject", "rejection_reason": "wrong UTR"},
            headers=admin_headers, timeout=20,
        )
        assert rej.status_code == 200, rej.text
        assert rej.json()["status"] == "rejected"

        # Verify history row shows rejected + reason
        h = requests.get(f"{API}/payments/manual/me?page_size=20", headers=user_headers, timeout=20).json()
        row = next((x for x in h["items"] if x["id"] == req_id), None)
        assert row is not None
        assert row["status"] == "rejected"
        assert row["rejection_reason"] == "wrong UTR"

        # Quote should now return normal (no pending)
        q2 = requests.get(f"{API}/payments/manual/quote?program_id={target['id']}",
                          headers=user_headers, timeout=20)
        assert q2.status_code == 200, q2.text
        assert q2.json()["pending_request"] is None

        # Resubmit → 201
        submit_body["utr"] = f"UTRREJ2{int(time.time())}"
        r2 = requests.post(f"{API}/payments/manual/submit", json=submit_body,
                           headers=user_headers, timeout=20)
        assert r2.status_code == 201, r2.text


# ---------- BRV regression -----------------------------------------------


class TestBRVRegression:
    def test_brv_still_passes(self, admin_headers):
        r = requests.get(f"{API}/admin/qa/brv", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        # Support either aggregate or per-test format
        overall = body.get("overall") or body.get("status")
        total = body.get("total") or body.get("total_count")
        passed = body.get("passed") or body.get("passed_count")
        if total is not None and passed is not None:
            assert total == 36
            assert passed == 36
        else:
            # try nested
            summary = body.get("summary", {})
            assert summary.get("passed") == 36 or overall == "PASS", body
