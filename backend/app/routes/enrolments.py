"""Enrolment + subscription endpoints (Razorpay AutoPay / UPI mandate).

Endpoints:
  * POST /programs/{program_id}/enrol-free          — free program enrolment
  * POST /payments/subscription/init                — start AutoPay mandate
  * POST /payments/subscription/{sid}/verify        — post-checkout reconcile
  * POST /payments/subscription/{sid}/cancel        — smart cancel
  * GET  /payments/subscription/me                  — user's subscriptions

Race-safe design (2026-02):
  - `/init` reuses an existing subscription row still in {created, authenticated,
    active, pending} instead of creating a duplicate. Rows in `created` state
    older than 60 minutes are treated as stale (Razorpay auto-expires those).
  - Every write is idempotent — `subscription.charged` webhooks dedupe by
    `razorpay_payment_id` so retries never double-grant access.
  - `/cancel` uses `cancel_at_cycle_end=True` when the mandate is active
    (user keeps paid access), `False` for pending mandates (Razorpay 400s
    the cycle-end flag on non-authenticated subs).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.deps import db, get_current_user
from app.services.payment import (
    FREQUENCY_TO_DAYS,
    cancel_subscription as rzp_cancel_subscription,
    create_plan as rzp_create_plan,
    create_subscription as rzp_create_subscription,
    fetch_subscription as rzp_fetch_subscription,
    fetch_subscription_payments as rzp_fetch_subscription_payments,
    is_mock as rzp_is_mock,
    key_id_for_frontend,
)
from app.utils.audit import log_action

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Payments · Enrolment"])

# Statuses that mean the local row is still usable (setup or actively
# charging). Terminal statuses (cancelled/completed/expired/halted) are
# ignored — the user starts fresh.
_REUSABLE_STATUSES = {"created", "authenticated", "active", "pending"}
_STALE_CREATED_MINUTES = 60


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
#  SUBSCRIPTION ENROLMENT (Razorpay AutoPay / UPI Mandate)
# ============================================================================

def _plan_cache_key(frequency: str, amount_paise: int) -> str:
    return f"{frequency}:{amount_paise}"


async def _compute_subscription_amount(
    database: AsyncIOMotorDatabase, program: dict
) -> tuple[int, dict]:
    """Server-side pricing so the client can't tamper."""
    price = float(program.get("price") or 0)
    discount = float(program.get("discount") or 0)
    row = await database.app_settings.find_one({"key": "default_gst_percent", "deleted_at": None})
    default_gst = float((row or {}).get("value") or 18)
    gst_pct = float(program.get("gst_percent") if program.get("gst_percent") is not None else default_gst)
    taxable = max(0.0, round(price - discount, 2))
    gst_amount = round((taxable * gst_pct) / 100.0, 2)
    total = round(taxable + gst_amount, 2)
    amount_paise = int(round(total * 100))
    if amount_paise <= 0:
        raise HTTPException(400, "Subscription amount must be greater than zero.")
    return amount_paise, {
        "price": price,
        "discount": discount,
        "taxable": taxable,
        "gst_percent": gst_pct,
        "gst_amount": gst_amount,
        "total": total,
    }


async def _get_or_create_plan(
    database: AsyncIOMotorDatabase,
    program: dict,
    frequency: str,
    amount_paise: int,
) -> tuple[str, bool]:
    """Return a Razorpay `plan_id` for the given (program, frequency, amount).

    Caches plan_ids in the `subscription_plans_cache` collection keyed by
    (program_id, frequency, amount_paise) so we never create a duplicate
    plan on Razorpay's side when a user re-subscribes. Cache is race-safe
    via a unique index and idempotent upsert.

    Returns `(plan_id, created_now)` where `created_now=True` means a
    fresh Razorpay Plan API call happened on this request.
    """
    key = {
        "program_id": program["id"],
        "frequency": frequency,
        "amount_paise": int(amount_paise),
    }
    cached = await database.subscription_plans_cache.find_one(
        {**key, "deleted_at": None}
    )
    if cached and cached.get("plan_id"):
        return cached["plan_id"], False

    plan = rzp_create_plan(
        amount_paise=amount_paise,
        frequency=frequency,
        program_name=program.get("name") or "RIYORA Subscription",
    )
    plan_id = plan["id"]
    now = _iso()
    await database.subscription_plans_cache.update_one(
        key,
        {
            "$set": {
                **key,
                "plan_id": plan_id,
                "is_mock": bool(plan.get("is_mock", False)),
                "updated_at": now,
                "deleted_at": None,
            },
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "created_at": now,
            },
        },
        upsert=True,
    )
    return plan_id, True


class SubscriptionInitRequest(BaseModel):
    program_id: str = Field(..., min_length=1)


def _friendly_razorpay_error(exc: Exception) -> str:
    """Translate Razorpay API errors into user-friendly messages.

    Common failures on a fresh account: Subscriptions feature not enabled
    (returns HTTP 400 with description like 'You are not authorized to use
    this feature'). We surface this clearly so the admin doesn't chase a
    non-existent code bug.
    """
    msg = str(exc)
    low = msg.lower()
    if any(k in low for k in ("not authorized", "not activated", "not enabled", "unauthorized")):
        return (
            "Razorpay Subscriptions is not enabled on your merchant account. "
            "Email sub-support@razorpay.com and ask them to activate "
            "Subscriptions + UPI AutoPay on your MID. Turnaround is 24-48 hours."
        )
    if "amount" in low and ("min" in low or "less" in low):
        return "Subscription amount is below Razorpay's minimum. Increase the program price."
    return f"Could not create subscription: {msg}"


@router.post("/payments/subscription/init", status_code=201)
async def subscription_init(
    body: SubscriptionInitRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    program = await database.programs.find_one(
        {"id": body.program_id, "deleted_at": None, "is_active": True}
    )
    if not program:
        raise HTTPException(404, "Program not found or inactive.")
    if program.get("payment_type") != "subscription":
        raise HTTPException(400, "This program is not a subscription.")
    frequency = program.get("subscription_frequency")
    if frequency not in FREQUENCY_TO_DAYS:
        raise HTTPException(400, "Program is missing a valid subscription_frequency.")

    membership_id = current["membership_id"]

    # Block re-subscribe if user has active access via any purchase.
    from app.services.validity import get_active_purchase
    active_purchase = await get_active_purchase(database, membership_id, body.program_id)
    if active_purchase:
        raise HTTPException(409, "You already have active access to this program.")

    amount_paise, breakdown = await _compute_subscription_amount(database, program)

    # ------------------------------------------------------------------
    # Race-safe reuse: return the existing usable subscription rather than
    # creating a duplicate mandate.
    # ------------------------------------------------------------------
    now_utc = datetime.now(timezone.utc)
    stale_cutoff = (now_utc - timedelta(minutes=_STALE_CREATED_MINUTES)).isoformat()

    reusable = await database.subscriptions.find_one(
        {
            "user_membership_id": membership_id,
            "program_id": body.program_id,
            "status": {"$in": list(_REUSABLE_STATUSES)},
            "deleted_at": None,
        },
        sort=[("created_at", -1)],
    )
    if reusable:
        is_created_stale = (
            reusable.get("status") == "created"
            and (reusable.get("created_at") or "") < stale_cutoff
        )
        if not is_created_stale:
            # Verify authoritative status on Razorpay before reusing.
            if not rzp_is_mock():
                fetched = rzp_fetch_subscription(reusable["subscription_id"])
                if fetched:
                    live_status = fetched.get("status")
                    if live_status in ("cancelled", "completed", "halted", "expired"):
                        await database.subscriptions.update_one(
                            {"_id": reusable["_id"]},
                            {"$set": {"status": live_status, "updated_at": _iso()}},
                        )
                        reusable = None

            if reusable:
                reusable.pop("_id", None)
                return {
                    "subscription_id": reusable["subscription_id"],
                    "plan_id": reusable.get("plan_id"),
                    "short_url": reusable.get("short_url"),
                    "key_id": key_id_for_frontend(),
                    "is_mock": bool(reusable.get("is_mock", False)),
                    "status": reusable.get("status"),
                    "breakdown": breakdown,
                    "amount_paise": amount_paise,
                    "program": {
                        "id": program["id"],
                        "name": program.get("name"),
                        "subscription_frequency": frequency,
                    },
                    "prefill": {
                        "name": current.get("full_name", ""),
                        "email": current.get("email", ""),
                        "contact": current.get("mobile", ""),
                    },
                    "reused": True,
                }
        else:
            await database.subscriptions.update_one(
                {"_id": reusable["_id"]},
                {"$set": {"status": "expired", "updated_at": _iso()}},
            )

    # ------------------------------------------------------------------
    # Fresh plan + subscription on Razorpay.
    # ------------------------------------------------------------------
    from app.services.sub_debug import log_event as _dbg
    await _dbg(
        database, source="backend", stage="init.start",
        program_id=body.program_id, membership_id=membership_id,
        payload={"frequency": frequency, "amount_paise": amount_paise, "breakdown": breakdown},
    )
    try:
        plan_id, created_now = await _get_or_create_plan(
            database, program, frequency, amount_paise,
        )
        await _dbg(
            database, source="backend", stage="init.plan_ok",
            program_id=body.program_id, membership_id=membership_id,
            payload={"plan_id": plan_id, "created_now": created_now, "source": "dynamic_cached"},
        )
        subscription = rzp_create_subscription(
            plan_id=plan_id,
            frequency=frequency,
            notes={
                "user_membership_id": membership_id,
                "program_id": body.program_id,
                "program_name": (program.get("name") or "")[:80],
            },
        )
        await _dbg(
            database, source="backend", stage="init.subscription_ok",
            subscription_id=subscription.get("id"), program_id=body.program_id,
            membership_id=membership_id,
            payload={
                "id": subscription.get("id"),
                "status": subscription.get("status"),
                "short_url": subscription.get("short_url"),
                "total_count": subscription.get("total_count"),
                "expire_by": subscription.get("expire_by"),
                "payment_method": subscription.get("payment_method"),
                "auth_attempts": subscription.get("auth_attempts"),
                "created_at": subscription.get("created_at"),
            },
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Razorpay subscription.create failed: %s", exc)
        await _dbg(
            database, source="backend", stage="init.error", ok=False,
            program_id=body.program_id, membership_id=membership_id,
            error={"type": type(exc).__name__, "message": str(exc), "args": [str(a) for a in exc.args]},
        )
        raise HTTPException(502, _friendly_razorpay_error(exc)) from exc

    doc = {
        "id": str(uuid.uuid4()),
        "subscription_id": subscription["id"],
        "plan_id": plan_id,
        "user_membership_id": membership_id,
        "program_id": body.program_id,
        "program_name": program.get("name"),
        "frequency": frequency,
        "amount_paise": amount_paise,
        "amount_rupees": breakdown["total"],
        "breakdown": breakdown,
        "total_count": subscription.get("total_count"),
        "paid_count": subscription.get("paid_count", 0),
        "short_url": subscription.get("short_url"),
        "status": subscription.get("status") or "created",
        "is_mock": bool(subscription.get("is_mock", rzp_is_mock())),
        "created_at": _iso(),
        "updated_at": _iso(),
        "deleted_at": None,
    }
    await database.subscriptions.insert_one(doc)
    await log_action(
        database,
        actor_id=membership_id,
        action="subscription.init",
        entity="subscription",
        entity_id=doc["subscription_id"],
        meta={"program_id": body.program_id, "frequency": frequency},
    )

    return {
        "subscription_id": doc["subscription_id"],
        "plan_id": doc["plan_id"],
        "short_url": doc["short_url"],
        "key_id": key_id_for_frontend(),
        "is_mock": doc["is_mock"],
        "status": doc["status"],
        "breakdown": breakdown,
        "amount_paise": amount_paise,
        "program": {
            "id": program["id"],
            "name": program.get("name"),
            "subscription_frequency": frequency,
        },
        "prefill": {
            "name": current.get("full_name", ""),
            "email": current.get("email", ""),
            "contact": current.get("mobile", ""),
        },
        "reused": False,
    }


@router.post("/payments/subscription/{subscription_id}/verify")
async def subscription_verify(
    subscription_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Post-checkout reconciliation. Fetches authoritative status from Razorpay,
    updates the local row, and materialises a `program_purchases` row if the
    first charge has been captured (idempotent).

    Webhook-independent: if Razorpay says `paid_count >= 1`, we materialise
    the purchase immediately using the actual payment_id from
    `subscription.fetch_payments`. This bypasses the webhook path entirely so
    users get access even if the merchant's webhook plumbing is misconfigured
    or delayed.
    """
    row = await database.subscriptions.find_one(
        {"subscription_id": subscription_id, "deleted_at": None}
    )
    if not row:
        raise HTTPException(404, "Subscription not found")
    if row["user_membership_id"] != current["membership_id"]:
        raise HTTPException(403, "Subscription does not belong to current user")

    live = rzp_fetch_subscription(subscription_id)
    live_status = (live or {}).get("status") or row.get("status")
    paid_count = (live or {}).get("paid_count", row.get("paid_count", 0))

    await database.subscriptions.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "status": live_status,
                "paid_count": paid_count,
                "updated_at": _iso(),
                **({"current_start": (live or {}).get("current_start")} if live else {}),
                **({"current_end": (live or {}).get("current_end")} if live else {}),
            }
        },
    )

    # Existing purchase for this subscription?
    purchase = await database.program_purchases.find_one(
        {
            "subscription_id": subscription_id,
            "user_membership_id": current["membership_id"],
            "deleted_at": None,
        },
        sort=[("purchase_date", -1)],
    )

    # ------------------------------------------------------------------
    # Webhook-independent materialisation.
    # Razorpay's SMS to the user says "Rs.X payment successful" the moment
    # the first charge is captured — `paid_count` reflects that on
    # `subscription.fetch`. If we see paid_count >= 1 and don't yet have a
    # purchase row, materialise it now using the real payment_id from
    # `subscription.fetch_payments`. This makes the flow work even when
    # the merchant's webhook endpoint is misconfigured.
    # ------------------------------------------------------------------
    if not purchase and not rzp_is_mock() and paid_count and int(paid_count) >= 1:
        payments = rzp_fetch_subscription_payments(subscription_id)
        # Filter to only captured/authorized payments so we don't pick up
        # a failed attempt.
        captured = [
            p for p in payments
            if (p.get("status") in ("captured", "authorized"))
        ]
        # Pick the latest captured payment (SDK returns newest-first).
        first_payment = captured[0] if captured else None
        if first_payment:
            purchase = await _materialise_subscription_purchase(
                database,
                subscription_row={**row, "paid_count": paid_count},
                razorpay_payment_id=first_payment["id"],
                cycle_index=int(paid_count),
            )
            # Reflect the transition locally so subsequent polls short-circuit.
            live_status = "active"
            await database.subscriptions.update_one(
                {"_id": row["_id"]},
                {"$set": {"status": "active", "updated_at": _iso()}},
            )
            from app.services.sub_debug import log_event as _dbg
            await _dbg(
                database, source="backend", stage="verify.materialised_from_api",
                subscription_id=subscription_id,
                membership_id=current["membership_id"],
                payload={"payment_id": first_payment["id"], "paid_count": paid_count},
            )

    # Mock mode: simulate a successful first charge on verify.
    if rzp_is_mock() and not purchase:
        purchase = await _materialise_subscription_purchase(
            database,
            subscription_row=row,
            razorpay_payment_id=f"pay_mock_sub_{uuid.uuid4().hex[:12]}",
            cycle_index=1,
        )
        live_status = "active"
        await database.subscriptions.update_one(
            {"_id": row["_id"]},
            {"$set": {"status": "active", "paid_count": 1, "updated_at": _iso()}},
        )

    return {
        "subscription_id": subscription_id,
        "status": live_status,
        "paid_count": paid_count,
        "purchase_id": purchase["id"] if purchase else None,
        "expiry_date": (purchase or {}).get("expiry_date"),
        "is_mock": bool(row.get("is_mock")),
    }


async def _materialise_subscription_purchase(
    database: AsyncIOMotorDatabase,
    subscription_row: dict,
    razorpay_payment_id: str,
    cycle_index: int | None = None,
) -> dict:
    """Idempotently create a `program_purchases` row for a subscription charge.

    Dedup on razorpay_payment_id. Fires commissions on every charge (per P0 spec
    that renewals grant commissions on each cycle).
    """
    from app.services.commission_engine import create_commissions_for_purchase
    from app.services.invoice import generate_invoice_pdf
    from app.services.validity import compute_expiry

    if razorpay_payment_id:
        existing = await database.program_purchases.find_one(
            {"razorpay_payment_id": razorpay_payment_id, "deleted_at": None}
        )
        if existing:
            existing.pop("_id", None)
            return existing

    # Cross-check by (subscription_id, cycle) so a webhook arriving after
    # `subscription_verify` has already materialised the row doesn't create
    # a duplicate purchase. Backfill payment_id if verify used a placeholder.
    if subscription_row.get("subscription_id") and cycle_index is not None:
        by_cycle = await database.program_purchases.find_one({
            "subscription_id": subscription_row["subscription_id"],
            "subscription_cycle": cycle_index,
            "deleted_at": None,
        })
        if by_cycle:
            if (
                razorpay_payment_id
                and by_cycle.get("razorpay_payment_id") != razorpay_payment_id
                and str(by_cycle.get("razorpay_payment_id", "")).startswith("pay_")  # only backfill placeholders
                is False
            ):
                # keep the earlier value; nothing to do
                pass
            by_cycle.pop("_id", None)
            return by_cycle

    program = await database.programs.find_one(
        {"id": subscription_row["program_id"], "deleted_at": None}
    )
    if not program:
        raise HTTPException(404, "Program disappeared")

    frequency = subscription_row.get("frequency", "monthly")
    cycle_days = FREQUENCY_TO_DAYS.get(frequency, int(program.get("validity_days") or 30))

    now = datetime.now(timezone.utc)
    expiry = compute_expiry(now, cycle_days)
    breakdown = subscription_row.get("breakdown") or {}
    invoice_number = f"SUB-{uuid.uuid4().hex[:12].upper()}"

    purchase_doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": subscription_row["user_membership_id"],
        "program_id": subscription_row["program_id"],
        "payment_order_id": None,
        "razorpay_order_id": None,
        "razorpay_payment_id": razorpay_payment_id,
        "subscription_id": subscription_row["subscription_id"],
        "subscription_cycle": cycle_index,
        "price_paid": breakdown.get("price", 0),
        "discount": breakdown.get("discount", 0),
        "taxable_amount": breakdown.get("taxable", 0),
        "gst_percent": breakdown.get("gst_percent", 18),
        "gst_amount": breakdown.get("gst_amount", 0),
        "total": breakdown.get("total", subscription_row.get("amount_rupees", 0)),
        "invoice_number": invoice_number,
        "purchase_date": now.isoformat(),
        "expiry_date": expiry.isoformat(),
        "renewal_date": None,
        "status": "active",
        "payment_status": "captured",
        "source": "razorpay_subscription",
        "is_mock": bool(subscription_row.get("is_mock", False)),
        "is_subscription": True,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "deleted_at": None,
    }
    await database.program_purchases.insert_one(purchase_doc)

    # Invoice PDF — best effort.
    try:
        user = await database.users.find_one(
            {"membership_id": subscription_row["user_membership_id"], "deleted_at": None}
        ) or {}
        gst_row = await database.app_settings.find_one(
            {"key": "company_gst_number", "deleted_at": None}
        )
        gst = (gst_row or {}).get("value", "")
        generate_invoice_pdf(purchase=purchase_doc, program=program, user=user, company_gst_number=gst)
    except Exception:  # noqa: BLE001
        logger.exception("Invoice PDF (subscription) failed")

    # Commissions on every cycle.
    try:
        await create_commissions_for_purchase(database, purchase_doc)
    except Exception:  # noqa: BLE001
        logger.exception("Commission engine (subscription) failed")

    # Notify.
    try:
        from app.services.notify import payment_success as _notify_success
        await _notify_success(
            database,
            membership_id=subscription_row["user_membership_id"],
            program_name=program.get("name", "your program"),
            amount=float(purchase_doc["total"]),
            source="razorpay_subscription",
        )
    except Exception:  # noqa: BLE001
        pass

    await database.activity_log.insert_one(
        {
            "id": str(uuid.uuid4()),
            "actor_membership_id": subscription_row["user_membership_id"],
            "action": "subscription.charged",
            "target": subscription_row["subscription_id"],
            "meta": {
                "program_id": subscription_row["program_id"],
                "amount": float(purchase_doc["total"]),
                "cycle": cycle_index,
            },
            "created_at": _iso(),
        }
    )
    return purchase_doc


@router.post("/payments/subscription/{subscription_id}/cancel")
async def subscription_cancel(
    subscription_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Smart cancel — cycle-end for active mandates, immediate for pending ones."""
    row = await database.subscriptions.find_one(
        {"subscription_id": subscription_id, "deleted_at": None}
    )
    if not row:
        raise HTTPException(404, "Subscription not found")
    if row["user_membership_id"] != current["membership_id"]:
        raise HTTPException(403, "Subscription does not belong to current user")
    if row.get("status") in ("cancelled", "completed", "expired"):
        return {"subscription_id": subscription_id, "status": row.get("status"), "already_terminal": True}

    live = rzp_fetch_subscription(subscription_id)
    live_status = (live or {}).get("status") or row.get("status") or "created"
    at_cycle_end = live_status in ("active", "authenticated")

    try:
        result = rzp_cancel_subscription(subscription_id, cancel_at_cycle_end=at_cycle_end)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Razorpay cancel failed: %s", exc)
        raise HTTPException(502, f"Could not cancel subscription: {exc}") from exc

    new_status = (result or {}).get("status") or "cancelled"
    await database.subscriptions.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "status": new_status,
                "cancelled_at": _iso(),
                "cancel_at_cycle_end": at_cycle_end,
                "updated_at": _iso(),
            }
        },
    )
    await log_action(
        database,
        actor_id=current["membership_id"],
        action="subscription.cancel",
        entity="subscription",
        entity_id=subscription_id,
        meta={"cancel_at_cycle_end": at_cycle_end, "status": new_status},
    )
    return {
        "subscription_id": subscription_id,
        "status": new_status,
        "cancel_at_cycle_end": at_cycle_end,
    }


@router.get("/payments/subscription/me")
async def my_subscriptions(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    items: list[dict[str, Any]] = []
    async for r in database.subscriptions.find(
        {"user_membership_id": current["membership_id"], "deleted_at": None}
    ).sort("created_at", -1):
        r.pop("_id", None)
        items.append(r)
    return {"items": items, "total": len(items)}


class SubDebugLogRequest(BaseModel):
    """Frontend-side telemetry from SubscriptionCheckoutModal. Any auth'd user
    can post; admin reviews aggregated events on /admin/qa/sub-debug."""
    stage: str = Field(..., min_length=1, max_length=80)
    subscription_id: str | None = None
    program_id: str | None = None
    ok: bool = True
    message: str = ""
    payload: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


@router.post("/payments/subscription/debug-log", status_code=204)
async def subscription_debug_log(
    body: SubDebugLogRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Client-side telemetry sink. The frontend fires this on every state
    transition (init request, Razorpay opened, payment.failed, etc.) so
    the admin can trace what happened without needing DevTools on the
    user's phone. Fire-and-forget from the client."""
    from app.services.sub_debug import log_event as _dbg
    await _dbg(
        database, source="frontend", stage=body.stage,
        subscription_id=body.subscription_id, program_id=body.program_id,
        membership_id=current.get("membership_id"),
        ok=body.ok, message=body.message,
        payload=body.payload, error=body.error,
    )
    return None
