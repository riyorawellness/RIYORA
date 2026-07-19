"""Razorpay payment service — supports both LIVE and MOCK modes.

Mock mode (`RAZORPAY_MOCK_MODE=true`) is fully functional for local/dev work:
  * `create_order` returns a synthetic `mock_ord_<uuid>` id
  * `verify_signature` accepts any signature that equals `mock_sig_<order_id>`
  * `verify_webhook_signature` returns True (payloads are still validated)

Live mode calls the real Razorpay Python SDK; all payment verification uses
HMAC-SHA256 with the account secret.

The two modes share the same public surface so the rest of the codebase never
knows the difference.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from typing import Any

import razorpay

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _client() -> razorpay.Client | None:
    if settings.RAZORPAY_MOCK_MODE:
        return None
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        logger.warning("Razorpay keys missing while MOCK mode is off — falling back to mock.")
        return None
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def key_id_for_frontend() -> str:
    """Return the public key id used by Checkout.js. Uses a placeholder
    when running in mock mode so the frontend can still identify the flow."""
    return settings.RAZORPAY_KEY_ID or "rzp_test_mock"


def is_mock() -> bool:
    return _client() is None


def create_order(
    amount_paise: int,
    receipt: str,
    notes: dict[str, Any] | None = None,
    currency: str = "INR",
) -> dict[str, Any]:
    """Create a Razorpay order. Returns the raw order dict (with `id`, `amount`)."""
    payload = {
        "amount": int(amount_paise),
        "currency": currency,
        "receipt": receipt[:40],
        "payment_capture": 1,
        "notes": notes or {},
    }
    client = _client()
    if client is None:
        return {
            "id": f"mock_ord_{uuid.uuid4().hex[:16]}",
            "amount": payload["amount"],
            "currency": currency,
            "receipt": payload["receipt"],
            "notes": payload["notes"],
            "status": "created",
            "created_at": None,
            "is_mock": True,
        }
    order = client.order.create(payload)
    order["is_mock"] = False
    return order


def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature.

    Live: HMAC-SHA256(order_id|payment_id, key_secret) == signature.
    Mock: accept `mock_sig_<order_id>`.
    """
    if is_mock():
        return signature == f"mock_sig_{order_id}"
    body = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(payload_bytes: bytes, signature: str, secret: str) -> bool:
    if is_mock() and signature.startswith("mock_"):
        return True
    if not secret:
        return False
    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------- Subscriptions ---------------------------------------------------
# NOTE (2026-07-21): Razorpay AutoPay/mandate subscriptions have been REMOVED.
# The UPI mandate flow was inherently unreliable in India — Checkout.js would
# show spurious "Payment Failed" modals even when the mandate was authenticated
# and money was debited, leading to double-charges and cancelled mandates when
# users retried. Subscription programs now use the SAME one-time Razorpay
# order flow as one-off purchases: the user pays for one cycle at a time,
# the purchase carries an expiry_date, and when it lapses the user clicks
# "Renew" to pay for another cycle. Simple, deterministic, no race conditions.

# Days per subscription cycle — used by admin create/update to auto-set
# program.validity_days when payment_type == "subscription".
FREQUENCY_TO_DAYS = {
    "monthly":     30,
    "half_yearly": 180,
    "yearly":      365,
}
