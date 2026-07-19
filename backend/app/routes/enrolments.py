"""Enrolment + Subscription endpoints (2026-02).

- Free programs → POST /api/programs/{id}/enrol-free creates a row in
  the new `program_enrolments` collection. No payment, no commissions.

- Subscription programs → real Razorpay AutoPay flow:
    POST /api/payments/subscription/init            (user starts)
    POST /api/payments/subscription/{sid}/verify    (post-Checkout)
    POST /api/payments/subscription/{sid}/cancel    (user cancels)

- Webhook `subscription.charged` (delivered to /api/payments/webhook)
  is handled inline in payments.py — that route already exists; we just
  add branch logic there. This file focuses on the new user-initiated
  endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.core.deps import db, get_current_user
from app.services import payment as pay_svc
from app.services.commission_engine import create_commissions_for_purchase
from app.utils.audit import log_action

router = APIRouter(tags=["Payments · Enrolment / Subscription"])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
#  FREE PROGRAM ENROLMENT
# ============================================================================

@router.post("/programs/{program_id}/enrol-free", status_code=201)
async def enrol_free(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    program = await database.programs.find_one({"id": program_id, "deleted_at": None, "is_active": True})
    if not program:
        raise HTTPException(404, "Program not found or inactive.")
    if program.get("payment_type") != "free":
        raise HTTPException(400, "This program is not free.")

    membership_id = current["membership_id"]
    existing = await database.program_enrolments.find_one(
        {"user_membership_id": membership_id, "program_id": program_id, "deleted_at": None}
    )
    if existing:
        raise HTTPException(409, "You are already enrolled in this program.")

    doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": membership_id,
        "program_id": program_id,
        "program_name": program.get("name"),
        "source": "free",
        "status": "active",
        "created_at": _iso(),
        "updated_at": _iso(),
        "deleted_at": None,
    }
    await database.program_enrolments.insert_one(doc)
    await log_action(
        database,
        actor_id=membership_id,
        action="enrol.free",
        entity="program",
        entity_id=program_id,
    )
    doc.pop("_id", None)
    return doc


@router.get("/programs/me/enrolments")
async def my_enrolments(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    out = []
    async for r in database.program_enrolments.find(
        {"user_membership_id": current["membership_id"], "deleted_at": None}
    ).sort("created_at", -1):
        r.pop("_id", None)
        out.append(r)
    return {"items": out, "total": len(out)}


# ============================================================================
#  SUBSCRIPTION — Razorpay AutoPay
# ============================================================================

class SubscriptionInitBody(BaseModel):
    program_id: str


@router.post("/payments/subscription/init", status_code=201)
async def subscription_init(
    body: SubscriptionInitBody,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Start a Razorpay subscription for the current user.

    Creates a Plan (or reuses cached), a Subscription, and stores the
    server-side record in `subscriptions` collection with status='created'.
    Frontend then opens Razorpay Checkout with `subscription_id`.
    """
    program = await database.programs.find_one(
        {"id": body.program_id, "deleted_at": None, "is_active": True}
    )
    if not program:
        raise HTTPException(404, "Program not found or inactive.")
    if program.get("payment_type") != "subscription":
        raise HTTPException(400, "This program is not a subscription.")
    freq = program.get("subscription_frequency")
    if freq not in {"monthly", "half_yearly", "yearly"}:
        raise HTTPException(400, "Program missing a valid subscription_frequency.")

    # Look for any prior subscription attempt for this (user, program). BEFORE
    # deciding whether to cancel or block, reconcile against Razorpay's
    # authoritative status — the local DB may lag behind reality.
    #
    # This was the source of a nasty production bug: users saw a spurious
    # "Payment Failed" on Checkout, our DB thought status='created', we
    # cancelled the row via Razorpay on retry — but Razorpay had actually
    # authenticated the mandate. The user then made a second payment,
    # Razorpay found the mandate cancelled, and rejected the whole
    # subscription with "Subscription was cancelled by Razorpay."
    now_iso = _iso()
    prior_cursor = database.subscriptions.find({
        "user_membership_id": current["membership_id"],
        "program_id": program["id"],
        "status": {"$nin": ["cancelled", "expired", "halted", "completed"]},
        "deleted_at": None,
    })
    async for prior in prior_cursor:
        sid_local = prior.get("subscription_id")
        live_status = prior.get("status")
        # Ask Razorpay for the real status. Skip lookup for mock sub_ids.
        if sid_local and not sid_local.startswith("mock_sub_"):
            try:
                live = pay_svc.fetch_subscription(sid_local)
                live_status = live.get("status") or live_status
                # Sync local status so program_status + wallet flows are honest.
                if live_status != prior.get("status"):
                    await database.subscriptions.update_one(
                        {"_id": prior["_id"]},
                        {"$set": {"status": live_status, "updated_at": now_iso}},
                    )
            except Exception:  # noqa: BLE001
                # If we can't reach Razorpay, err on the side of NOT cancelling
                # — cancelling a live mandate is far worse than blocking a retry.
                live_status = live_status or "unknown"

        # Any state that means Razorpay considers the subscription valid
        # → block the retry, do NOT cancel it.
        if live_status in {"authenticated", "active", "pending", "unknown"}:
            raise HTTPException(
                409,
                "You already have a subscription in progress for this program. "
                "If your bank has debited you, it will unlock within a minute. "
                "Please refresh — do not create a duplicate.",
            )
        # Truly abandoned (status='created' at Razorpay side too) → safe to
        # cancel locally + on Razorpay so the retry can create a fresh sub.
        if live_status == "created":
            try:
                pay_svc.cancel_subscription(sid_local or "", cancel_at_cycle_end=False)
            except Exception:  # noqa: BLE001
                pass
            await database.subscriptions.update_one(
                {"_id": prior["_id"]},
                {"$set": {
                    "status": "cancelled", "cancelled_at": now_iso,
                    "updated_at": now_iso, "cancel_reason": "abandoned_retry_verified",
                }},
            )

    # Amount in paise (Razorpay Plans require the amount baked-in).
    price = float(program.get("price", 0) or 0)
    discount = float(program.get("discount", 0) or 0)
    net = max(0.0, price - discount)
    gst_pct = float(program.get("gst_percent", 0) or 0)
    total_inr = round(net + net * gst_pct / 100, 2)
    amount_paise = int(round(total_inr * 100))

    # Create (or reuse) Razorpay Plan. We cache the plan_id per
    # (program, frequency, amount) on the program doc so the admin doesn't
    # rack up duplicate Razorpay Plans every time a user subscribes.
    cache_key = f"{freq}:{amount_paise}"
    cached = (program.get("_razorpay_plans") or {}).get(cache_key)
    plan_id = cached
    if not plan_id:
        try:
            plan_id = pay_svc.create_or_reuse_plan(
                program_id=program["id"],
                program_name=program.get("name", "RIYORA program"),
                frequency=freq,
                amount_paise=amount_paise,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Razorpay plan creation failed: {exc}") from exc
        # Persist the plan_id so subsequent subscribers reuse it.
        await database.programs.update_one(
            {"id": program["id"]},
            {"$set": {f"_razorpay_plans.{cache_key}": plan_id}},
        )

    # Create the Subscription (frequency-aware total_count so we don't
    # trip Razorpay's 100-count and 30-year UPI expire_at caps).
    try:
        sub = pay_svc.create_subscription(
            plan_id=plan_id,
            frequency=freq,
            notes={
                "membership_id": current["membership_id"],
                "program_id": program["id"],
                "program_name": program.get("name"),
                "frequency": freq,
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Razorpay subscription creation failed: {exc}") from exc

    now = _iso()
    doc = {
        "subscription_id": sub["id"],
        "user_membership_id": current["membership_id"],
        "program_id": program["id"],
        "program_name": program.get("name"),
        "plan_id": plan_id,
        "frequency": freq,
        "amount_paise": amount_paise,
        "status": sub.get("status", "created"),
        "short_url": sub.get("short_url"),
        "is_mock": bool(sub.get("is_mock")),
        "created_at": now,
        "updated_at": now,
        "activated_at": None,
        "cancelled_at": None,
        "charges_count": 0,
        "deleted_at": None,
    }
    await database.subscriptions.insert_one(doc)
    await log_action(
        database,
        actor_id=current["membership_id"],
        action="subscription.init",
        entity="subscription",
        entity_id=sub["id"],
        meta={"program_id": program["id"], "plan_id": plan_id, "frequency": freq},
    )
    doc.pop("_id", None)
    return {
        "subscription_id": sub["id"],
        "plan_id": plan_id,
        "amount_paise": amount_paise,
        "frequency": freq,
        "short_url": sub.get("short_url"),
        "razorpay_key_id": pay_svc.key_id_for_frontend(),
        "is_mock": bool(sub.get("is_mock")),
    }


@router.post("/payments/subscription/{sub_id}/verify")
async def subscription_verify(
    sub_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Called by the frontend after Razorpay Checkout completes the mandate
    setup. Fetches live status from Razorpay and updates our record.
    On mock mode we optimistically mark it authenticated so tests can
    proceed without going through the real Razorpay checkout.
    """
    doc = await database.subscriptions.find_one(
        {"subscription_id": sub_id, "user_membership_id": current["membership_id"], "deleted_at": None}
    )
    if not doc:
        raise HTTPException(404, "Subscription not found.")

    try:
        live = pay_svc.fetch_subscription(sub_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Razorpay fetch failed: {exc}") from exc

    status = live.get("status", "created")
    now = _iso()
    updates = {"status": status, "updated_at": now}
    # `active` means Razorpay has already collected at least one charge —
    # this is the moment access is granted. `authenticated` (mandate set
    # up but not yet charged) is deliberately NOT enough to unlock.
    if status == "active" and not doc.get("activated_at"):
        updates["activated_at"] = now
    await database.subscriptions.update_one({"_id": doc["_id"]}, {"$set": updates})
    return {"subscription_id": sub_id, "status": status}


@router.post("/payments/subscription/{sub_id}/cancel")
async def subscription_cancel(
    sub_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """User-initiated cancel. Access preserved until current cycle ends."""
    doc = await database.subscriptions.find_one(
        {"subscription_id": sub_id, "user_membership_id": current["membership_id"], "deleted_at": None}
    )
    if not doc:
        raise HTTPException(404, "Subscription not found.")
    if doc["status"] in {"cancelled", "completed", "expired", "halted"}:
        raise HTTPException(409, f"Subscription already {doc['status']}.")

    try:
        # For unauthenticated/created mandates Razorpay refuses
        # cancel_at_cycle_end=1 (there is no cycle yet). Fall back to
        # immediate cancel so the user can back out.
        cancel_at_end = doc["status"] not in {"created", "pending"}
        pay_svc.cancel_subscription(sub_id, cancel_at_cycle_end=cancel_at_end)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Razorpay cancel failed: {exc}") from exc

    now = _iso()
    await database.subscriptions.update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "cancelled", "cancelled_at": now, "updated_at": now}},
    )
    await log_action(
        database,
        actor_id=current["membership_id"],
        action="subscription.cancel",
        entity="subscription",
        entity_id=sub_id,
    )
    return {"subscription_id": sub_id, "status": "cancelled"}


@router.get("/payments/subscription/me")
async def my_subscriptions(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    out = []
    async for r in database.subscriptions.find(
        {"user_membership_id": current["membership_id"], "deleted_at": None}
    ).sort("created_at", -1):
        r.pop("_id", None)
        out.append(r)
    return {"items": out, "total": len(out)}


@router.post("/payments/subscription/reconcile-mine")
async def reconcile_my_subscriptions(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Sync every non-terminal subscription of the current user against
    Razorpay's authoritative state. Useful when webhooks are delayed or
    when the user got stuck after a Checkout race — they can hit this
    endpoint (or the frontend can call it on program load) and the local
    DB will catch up to reality without any risky cancels."""
    updates: list[dict] = []
    async for row in database.subscriptions.find({
        "user_membership_id": current["membership_id"],
        "status": {"$nin": ["cancelled", "expired", "halted", "completed"]},
        "deleted_at": None,
    }):
        sid = row.get("subscription_id")
        if not sid or sid.startswith("mock_sub_"):
            continue
        try:
            live = pay_svc.fetch_subscription(sid)
            new_status = live.get("status") or row.get("status")
        except Exception:  # noqa: BLE001
            continue
        if new_status != row.get("status"):
            patch = {"status": new_status, "updated_at": _iso()}
            if new_status == "active" and not row.get("activated_at"):
                patch["activated_at"] = _iso()
            await database.subscriptions.update_one({"_id": row["_id"]}, {"$set": patch})
            updates.append({"subscription_id": sid, "was": row.get("status"), "now": new_status})
    return {"updated": len(updates), "changes": updates}


# ============================================================================
#  Webhook branch — called from payments.py's existing /webhook route.
#  Exposed as a plain async function so payments.py can dispatch on event.
# ============================================================================

async def handle_subscription_charged(db_conn: AsyncIOMotorDatabase, payload: dict) -> None:
    """`subscription.charged` webhook — a mandate auto-charge succeeded.

    Insert a purchase row + trigger L1/L2/L3 commissions on EVERY renewal
    (per product requirement 3a). Idempotent: if we've already processed
    this Razorpay payment_id we return early.
    """
    entity = ((payload.get("payload") or {}).get("subscription") or {}).get("entity") or {}
    payment = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
    sub_id = entity.get("id")
    payment_id = payment.get("id")
    amount_paise = int(payment.get("amount") or 0)
    if not sub_id or not payment_id or amount_paise <= 0:
        return

    # Idempotency: skip if this payment_id is already recorded.
    if await db_conn.program_purchases.find_one({"razorpay_payment_id": payment_id}):
        return

    sub_doc = await db_conn.subscriptions.find_one({"subscription_id": sub_id, "deleted_at": None})
    if not sub_doc:
        return  # unknown subscription, ignore silently
    program = await db_conn.programs.find_one({"id": sub_doc["program_id"], "deleted_at": None}) or {}

    now = _iso()
    total = round(amount_paise / 100, 2)
    gst_pct = float(program.get("gst_percent", 0) or 0)
    taxable = round(total / (1 + gst_pct / 100), 2) if gst_pct else total
    gst_amount = round(total - taxable, 2)

    purchase_id = str(uuid.uuid4())
    invoice_number = f"INV-{purchase_id[:8].upper()}"
    purchase_doc = {
        "id": purchase_id,
        "user_membership_id": sub_doc["user_membership_id"],
        "program_id": sub_doc["program_id"],
        "price_paid": taxable,
        "discount": 0,
        "gst_amount": gst_amount,
        "total": total,
        "invoice_number": invoice_number,
        "purchase_date": now,
        "expiry_date": None,
        "status": "active",
        "source": "subscription",
        "razorpay_subscription_id": sub_id,
        "razorpay_payment_id": payment_id,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    await db_conn.program_purchases.insert_one(purchase_doc)

    # Advance the subscription record.
    await db_conn.subscriptions.update_one(
        {"_id": sub_doc["_id"]},
        {"$inc": {"charges_count": 1}, "$set": {"status": "active", "updated_at": now}},
    )

    # Trigger commissions on every renewal (product decision 3a).
    try:
        await create_commissions_for_purchase(db_conn, purchase_doc)
    except Exception:  # noqa: BLE001
        # Do not fail the webhook — commissions can be re-run by admin.
        import logging
        logging.getLogger(__name__).exception("commission_engine failed on subscription.charged")


async def handle_subscription_lifecycle(db_conn: AsyncIOMotorDatabase, payload: dict, event: str) -> None:
    """`subscription.pending|halted|cancelled|completed` — update status."""
    entity = ((payload.get("payload") or {}).get("subscription") or {}).get("entity") or {}
    sub_id = entity.get("id")
    if not sub_id:
        return
    status_map = {
        "subscription.pending": "pending",
        "subscription.halted": "halted",
        "subscription.cancelled": "cancelled",
        "subscription.completed": "completed",
    }
    new_status = status_map.get(event)
    if not new_status:
        return
    now = _iso()
    updates: dict = {"status": new_status, "updated_at": now}
    if new_status == "cancelled":
        updates["cancelled_at"] = now
    await db_conn.subscriptions.update_one(
        {"subscription_id": sub_id, "deleted_at": None},
        {"$set": updates},
    )
