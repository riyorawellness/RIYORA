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


# ---------- Subscriptions (Razorpay AutoPay / eMandate) --------------------
# Days per subscription cycle — used by admin create/update to auto-set
# program.validity_days when payment_type == "subscription".
FREQUENCY_TO_DAYS = {
    "monthly":     30,
    "quarterly":   90,
    "half_yearly": 180,
    "yearly":      365,
}

# Razorpay Plan `period` mapping — used at runtime by `create_plan()` to
# build the Razorpay plan payload for the given frequency.
FREQUENCY_TO_PLAN = {
    "monthly":     {"period": "monthly", "interval": 1},
    "quarterly":   {"period": "monthly", "interval": 3},
    "half_yearly": {"period": "monthly", "interval": 6},
    "yearly":      {"period": "yearly",  "interval": 1},
}

# UPI-safe `total_count` caps. Razorpay computes expire_at = now + (total_count
# × cycle_length). UPI/NPCI mandates cannot exceed ~30 years, and in practice
# many banks reject mandates > 10 years. We cap at ~5-10 years per frequency
# — when the count is exhausted, subscription.completed fires and the user
# simply re-subscribes.
#   monthly     × 60 cycles = 5 years
#   quarterly   × 40 cycles = 10 years
#   half_yearly × 20 cycles = 10 years
#   yearly      × 10 cycles = 10 years
FREQUENCY_TO_TOTAL_COUNT = {
    "monthly":     60,
    "quarterly":   40,
    "half_yearly": 20,
    "yearly":      10,
}


def create_plan(
    amount_paise: int,
    frequency: str,
    program_name: str,
    currency: str = "INR",
) -> dict[str, Any]:
    """Create (or return a mock) Razorpay Plan for the given amount+frequency.
    Callers are expected to cache the resulting `plan_id` per
    (program_id, frequency, amount_paise) to avoid duplicate plans on
    Razorpay's side."""
    if frequency not in FREQUENCY_TO_PLAN:
        raise ValueError(f"Unsupported frequency: {frequency}")
    spec = FREQUENCY_TO_PLAN[frequency]
    payload = {
        "period": spec["period"],
        "interval": spec["interval"],
        "item": {
            "name": (program_name or "RIYORA Subscription")[:200],
            "amount": int(amount_paise),
            "currency": currency,
        },
        "notes": {"frequency": frequency},
    }
    logger.info("[RZP.plan.create] payload=%s", payload)
    client = _client()
    if client is None:
        return {
            "id": f"mock_plan_{uuid.uuid4().hex[:16]}",
            "period": spec["period"],
            "interval": spec["interval"],
            "item": payload["item"],
            "is_mock": True,
        }
    plan = client.plan.create(payload)
    logger.info("[RZP.plan.create] response id=%s status=%s", plan.get("id"), plan.get("status"))
    plan["is_mock"] = False
    return plan


def create_subscription(
    plan_id: str,
    frequency: str,
    notes: dict[str, Any] | None = None,
    customer_notify: int = 1,
) -> dict[str, Any]:
    """Create a Razorpay Subscription bound to `plan_id`."""
    total_count = FREQUENCY_TO_TOTAL_COUNT.get(frequency, 12)
    payload: dict[str, Any] = {
        "plan_id": plan_id,
        "total_count": total_count,
        "quantity": 1,
        "customer_notify": customer_notify,
        "notes": notes or {},
    }
    logger.info("[RZP.subscription.create] payload=%s", payload)
    client = _client()
    if client is None:
        sid = f"mock_sub_{uuid.uuid4().hex[:16]}"
        return {
            "id": sid,
            "plan_id": plan_id,
            "status": "created",
            "total_count": total_count,
            "paid_count": 0,
            "short_url": f"https://rzp.io/mock/{sid}",
            "notes": payload["notes"],
            "is_mock": True,
        }
    sub = client.subscription.create(payload)
    logger.info(
        "[RZP.subscription.create] response id=%s status=%s short_url=%s expire_by=%s "
        "payment_method=%s auth_attempts=%s",
        sub.get("id"), sub.get("status"), sub.get("short_url"), sub.get("expire_by"),
        sub.get("payment_method"), sub.get("auth_attempts"),
    )
    sub["is_mock"] = False
    return sub


def fetch_subscription(subscription_id: str) -> dict[str, Any] | None:
    """Fetch current subscription status from Razorpay. Returns None on error."""
    client = _client()
    if client is None:
        return None
    try:
        s = client.subscription.fetch(subscription_id)
        logger.info(
            "[RZP.subscription.fetch] id=%s status=%s paid_count=%s payment_method=%s",
            s.get("id"), s.get("status"), s.get("paid_count"), s.get("payment_method"),
        )
        return s
    except Exception as exc:  # noqa: BLE001
        logger.warning("[RZP.subscription.fetch] %s failed: %s", subscription_id, exc)
        return None


def fetch_subscription_payments(subscription_id: str) -> list[dict[str, Any]]:
    """Fetch the payments already captured against a subscription.

    Used by `subscription_verify` to materialise a `program_purchases` row
    the moment Razorpay confirms the first charge — without depending on
    the merchant's webhook plumbing. Returns a list newest-first; empty
    on any error or mock mode.
    """
    client = _client()
    if client is None:
        return []
    try:
        # Razorpay Python SDK: /v1/subscriptions/{id}/payments
        # Some SDK versions expose this via `subscription.fetch_payments`,
        # others require raw payment.all() with a filter. Try both.
        if hasattr(client.subscription, "fetch_payments"):
            resp = client.subscription.fetch_payments(subscription_id)  # type: ignore[attr-defined]
        else:
            resp = client.payment.all({"subscription_id": subscription_id, "count": 10})
        items = resp.get("items", []) if isinstance(resp, dict) else (resp or [])
        logger.info(
            "[RZP.subscription.fetch_payments] id=%s payments=%d",
            subscription_id, len(items),
        )
        return items
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[RZP.subscription.fetch_payments] %s failed: %s", subscription_id, exc,
        )
        return []


def cancel_subscription(
    subscription_id: str, cancel_at_cycle_end: bool = True
) -> dict[str, Any]:
    """Cancel a Razorpay subscription.

    Razorpay refuses `cancel_at_cycle_end=True` on subscriptions still in
    `created`/`pending` (mandate never authenticated). Callers should
    branch on live status.
    """
    client = _client()
    if client is None:
        return {"id": subscription_id, "status": "cancelled", "is_mock": True}
    return client.subscription.cancel(
        subscription_id, {"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0}
    )
