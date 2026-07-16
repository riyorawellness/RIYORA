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


# ---------- Subscriptions (Razorpay AutoPay — LIVE + MOCK) -----------------

# Razorpay period + interval mapping for our 3 supported frequencies.
_FREQ_MAP = {
    "monthly":     {"period": "monthly", "interval": 1},
    "half_yearly": {"period": "monthly", "interval": 6},   # RP has no half_yearly; 6 monthly cycles.
    "yearly":      {"period": "yearly",  "interval": 1},
}


def create_or_reuse_plan(*, program_id: str, program_name: str,
                        frequency: str, amount_paise: int) -> str:
    """Create a Razorpay Plan for this program+frequency, or reuse if it
    already exists. Returns the plan_id string.

    NOTE: Razorpay Plans are immutable once created (amount/period are
    baked in). If admin edits price/frequency, we always create a NEW
    plan — old subscriptions keep charging at their original terms until
    they cancel or renewal is halted.
    """
    freq = _FREQ_MAP.get(frequency)
    if not freq:
        raise ValueError(f"Unsupported subscription frequency: {frequency}")
    plan_notes = {"program_id": program_id, "frequency": frequency, "amount": amount_paise}
    client = _client()
    if client is None:
        return f"mock_plan_{program_id}_{frequency}_{amount_paise}"

    plan = client.plan.create({
        "period": freq["period"],
        "interval": freq["interval"],
        "item": {
            "name": f"{program_name} ({frequency})"[:150],
            "amount": int(amount_paise),
            "currency": "INR",
        },
        "notes": plan_notes,
    })
    return plan["id"]


def create_subscription(*, plan_id: str, notes: dict[str, Any],
                       total_count: int = 120) -> dict[str, Any]:
    """Create a Razorpay Subscription against a plan. `total_count` is the
    maximum number of successful charges before the subscription ends —
    120 = 10 years for monthly, plenty of runway. User can cancel any time.

    Returns dict with `id`, `short_url`, `status`, `plan_id`. The
    frontend passes `id` to Checkout as `subscription_id` (NOT order_id).
    """
    client = _client()
    if client is None:
        return {
            "id": f"mock_sub_{uuid.uuid4().hex[:16]}",
            "plan_id": plan_id,
            "status": "created",
            "short_url": None,
            "is_mock": True,
        }
    sub = client.subscription.create({
        "plan_id": plan_id,
        "total_count": int(total_count),
        "customer_notify": 1,
        "notes": notes or {},
    })
    sub["is_mock"] = False
    return sub


def fetch_subscription(sub_id: str) -> dict[str, Any]:
    """Fetch current status of a subscription from Razorpay."""
    client = _client()
    if client is None:
        # Mock — pretend it's active. Real prod always calls the API.
        return {"id": sub_id, "status": "active", "is_mock": True}
    return client.subscription.fetch(sub_id)


def cancel_subscription(sub_id: str, cancel_at_cycle_end: bool = True) -> dict[str, Any]:
    """Cancel a subscription. `cancel_at_cycle_end=True` (default) lets
    the user keep access until the current period ends."""
    client = _client()
    if client is None:
        return {"id": sub_id, "status": "cancelled", "is_mock": True}
    return client.subscription.cancel(sub_id, {"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0})


# Legacy mock helper — kept for any legacy caller that still imports it.
def create_subscription_mock(program_id: str, plan: str) -> dict[str, Any]:
    return {
        "id": f"mock_sub_{uuid.uuid4().hex[:16]}",
        "plan_id": f"plan_{program_id}_{plan}",
        "status": "active",
        "plan": plan,
        "customer_notify": 1,
    }
