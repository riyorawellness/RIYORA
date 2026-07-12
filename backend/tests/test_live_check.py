"""Live Integration Check — /api/admin/qa/live-check/* tests.

Non-destructive: only creates mock orders in the current dev env, and calls
MSG91 dry-run which either falls back to dev mode or reports success.
"""
from __future__ import annotations

import os
import requests


def _base() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        env = "/app/frontend/.env"
        if os.path.exists(env):
            for line in open(env):
                line = line.strip()
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    assert url
    return url.rstrip("/") + "/api"


API = _base()


def _admin_token() -> str:
    r = requests.post(
        f"{API}/admin/login",
        json={"mobile": "9999999999", "password": "Admin@12345"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["tokens"]["access_token"]


def _hdr(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


# ---------- STATUS -------------------------------------------------------


def test_live_check_status_admin_only():
    r = requests.get(f"{API}/admin/qa/live-check/status", timeout=10)
    assert r.status_code in (401, 403)


def test_live_check_status_shape():
    t = _admin_token()
    r = requests.get(f"{API}/admin/qa/live-check/status", headers=_hdr(t), timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "razorpay" in body and "msg91" in body and "generated_at" in body

    rzp = body["razorpay"]
    for k in ("mock_mode", "is_mock_effective", "key_id_masked", "is_live_key",
              "has_secret", "has_webhook_secret", "webhook_url_hint", "status"):
        assert k in rzp
    assert rzp["status"] in ("live", "mock")

    sms = body["msg91"]
    for k in ("otp_dev_mode", "configured", "auth_key_masked",
              "template_id", "sender_id", "status"):
        assert k in sms
    assert sms["status"] in ("live", "dev")

    # Secrets must be masked, not leaked
    if rzp["key_id_masked"]:
        assert "…" in rzp["key_id_masked"] or len(rzp["key_id_masked"]) <= 3


# ---------- TEST ORDER ---------------------------------------------------


def test_live_check_test_order_creates_mock_or_live():
    t = _admin_token()
    r = requests.post(
        f"{API}/admin/qa/live-check/razorpay/test-order",
        headers=_hdr(t),
        json={"amount_paise": 100},
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["amount_paise"] == 100
    assert body["currency"] == "INR"
    assert body["order_id"]
    assert body["receipt"].startswith("livecheck_")
    assert body["key_id"]
    assert body["notes"]["diagnostic"] == "live-check"
    assert body["notes"]["admin_mobile"] == "9999999999"


def test_live_check_test_order_amount_bounds():
    t = _admin_token()
    # Too small
    r = requests.post(
        f"{API}/admin/qa/live-check/razorpay/test-order",
        headers=_hdr(t), json={"amount_paise": 50}, timeout=10,
    )
    assert r.status_code == 422
    # Too large
    r2 = requests.post(
        f"{API}/admin/qa/live-check/razorpay/test-order",
        headers=_hdr(t), json={"amount_paise": 100001}, timeout=10,
    )
    assert r2.status_code == 422


def test_live_check_test_order_requires_admin():
    r = requests.post(
        f"{API}/admin/qa/live-check/razorpay/test-order",
        json={"amount_paise": 100},
        timeout=10,
    )
    assert r.status_code in (401, 403)


# ---------- WEBHOOK EVENTS ----------------------------------------------


def test_live_check_webhook_events_list():
    t = _admin_token()
    r = requests.get(f"{API}/admin/qa/live-check/webhook-events?limit=5", headers=_hdr(t), timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "events" in body and "count" in body
    assert isinstance(body["events"], list)
    assert body["count"] == len(body["events"])
    assert body["count"] <= 5


def test_live_check_webhook_captures_incoming():
    """Fire a fake webhook and ensure it shows up in /webhook-events."""
    t = _admin_token()
    # Post a mock event (mock signature accepted in mock mode)
    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_mock_livecheck_1"}}},
    }
    r = requests.post(
        f"{API}/payments/webhook",
        json=payload,
        headers={"X-Razorpay-Signature": "mock_livecheck"},
        timeout=10,
    )
    assert r.status_code == 200

    r2 = requests.get(f"{API}/admin/qa/live-check/webhook-events?limit=25", headers=_hdr(t), timeout=10)
    assert r2.status_code == 200
    events = r2.json()["events"]
    # Must contain at least our fresh event.
    assert any(e.get("event") == "payment.captured" for e in events)


# ---------- MSG91 DRY RUN -----------------------------------------------


def test_live_check_msg91_dryrun():
    t = _admin_token()
    r = requests.post(
        f"{API}/admin/qa/live-check/msg91/dry-run",
        headers=_hdr(t),
        json={"mobile": "9876543210"},
        timeout=15,
    )
    # Either dev mode (not configured → sent=false) or live-configured (sent=true)
    assert r.status_code in (200, 502)
    if r.status_code == 200:
        body = r.json()
        assert "sent" in body and "dev_mode" in body
        assert isinstance(body["sent"], bool)


def test_live_check_msg91_validates_mobile():
    t = _admin_token()
    r = requests.post(
        f"{API}/admin/qa/live-check/msg91/dry-run",
        headers=_hdr(t),
        json={"mobile": "123"},  # too short
        timeout=10,
    )
    assert r.status_code == 422
