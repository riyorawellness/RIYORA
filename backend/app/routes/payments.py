"""Razorpay Payment Engine — all payment-related routes.

Flow:
    1. POST /api/payments/order      — server creates razor order, saves pending
    2. POST /api/payments/verify     — server verifies signature, activates purchase,
                                        generates invoice, opens program access
    3. POST /api/payments/webhook    — razor webhook (backup source of truth)
    4. GET  /api/payments/config     — public key id + is_mock flag
    5. GET  /api/payments/me         — my payment history
    6. GET  /api/payments/invoice/{purchase_id} — download my invoice PDF
    7. POST /api/payments/subscription — mock AutoPay subscription creation

Admin:
    GET  /api/payments/admin/transactions
    POST /api/payments/admin/transactions/{id}/refund   (mock)
    GET  /api/payments/admin/settings                    (GST etc.)
    PUT  /api/payments/admin/settings

**Content access lives on the purchase — this route is the ONLY code path
allowed to insert an `active` row into program_purchases.**
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import PaginatedResponse
from app.models.phase5 import (
    CreateOrderRequest,
    CreateOrderResponse,
    PaymentSettingsUpdate,
    RefundRequest,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    WebhookAck,
)
from app.repositories.base import BaseRepository
from app.services.invoice import INVOICE_DIR, generate_invoice_pdf
from app.services.payment import (
    create_order as rzp_create_order,
    is_mock as rzp_is_mock,
    key_id_for_frontend,
    verify_signature,
    verify_webhook_signature,
)
from app.services.commission_engine import create_commissions_for_purchase
from app.services.program_engine import check_purchase_allowed
from app.services.validity import compute_expiry, get_active_purchase

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/payments", tags=["Payments"])


# ---------------- helpers --------------------------------------------------


def _orders_repo(database) -> BaseRepository:
    return BaseRepository(database, "payment_orders", ["receipt", "order_id"], "-created_at")


def _subs_repo(database) -> BaseRepository:
    return BaseRepository(database, "subscriptions", ["plan"], "-created_at")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_setting(database: AsyncIOMotorDatabase, key: str, default: Any = None) -> Any:
    row = await database.app_settings.find_one({"key": key, "deleted_at": None})
    return (row or {}).get("value", default)


async def _compute_breakdown(database: AsyncIOMotorDatabase, program: dict) -> dict:
    """Server-side pricing so the client can't tamper with amounts."""
    price = float(program.get("price") or 0)
    discount = float(program.get("discount") or 0)
    default_gst = float(await _get_setting(database, "default_gst_percent", settings.DEFAULT_GST_PERCENT) or 18)
    gst_pct = float(program.get("gst_percent") if program.get("gst_percent") is not None else default_gst)
    taxable = max(0.0, round(price - discount, 2))
    gst_amount = round((taxable * gst_pct) / 100.0, 2)
    total = round(taxable + gst_amount, 2)
    return {
        "price": price,
        "discount": discount,
        "taxable": taxable,
        "gst_percent": gst_pct,
        "gst_amount": gst_amount,
        "total": total,
    }


# ---------------- config ---------------------------------------------------


@router.get("/config")
async def get_payment_config(_current: dict = Depends(get_current_user)):
    return {
        "key_id": key_id_for_frontend(),
        "is_mock": rzp_is_mock(),
        "currency": "INR",
        "checkout_theme": {"color": "#0B1A5B"},
    }



# ---------------- dummy user Mark-as-Paid ---------------------------------


@router.post("/mark-paid", status_code=201)
async def mark_paid_dummy(
    body: CreateOrderRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Grant a dummy (tester) user free access to a program.

    Only callable by users with `is_dummy=True`. Creates a `program_purchases`
    row with `source='dummy'` and `is_dummy=True` so revenue reports and
    analytics filter it out. NO commission engine, NO invoice PDF, NO gateway
    call, NO notifications.
    """
    if not current.get("is_dummy"):
        raise HTTPException(
            status_code=403,
            detail="Mark-as-Paid is only available for dummy (tester) accounts.",
        )

    program = await database.programs.find_one(
        {"id": body.program_id, "deleted_at": None, "is_active": True}
    )
    if not program:
        raise HTTPException(404, "Program not found")

    # Existing active access? Return idempotent success.
    active = await get_active_purchase(database, current["membership_id"], body.program_id)
    if active:
        return {
            "success": True,
            "purchase_id": active["id"],
            "already_active": True,
            "program_id": body.program_id,
            "expiry_date": active["expiry_date"],
        }

    breakdown = await _compute_breakdown(database, program)
    now = datetime.now(timezone.utc)
    expiry = compute_expiry(now, int(program.get("validity_days") or 365))
    invoice_number = f"TEST-{uuid.uuid4().hex[:10].upper()}"

    purchase_doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": current["membership_id"],
        "program_id": body.program_id,
        "payment_order_id": None,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "price_paid": breakdown["price"],
        "discount": breakdown["discount"],
        "taxable_amount": breakdown["taxable"],
        "gst_percent": breakdown["gst_percent"],
        "gst_amount": breakdown["gst_amount"],
        "total": breakdown["total"],
        "invoice_number": invoice_number,
        "purchase_date": now.isoformat(),
        "expiry_date": expiry.isoformat(),
        "renewal_date": None,
        "status": "active",
        "payment_status": "dummy",
        "source": "dummy",
        "is_mock": True,
        "is_dummy": True,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "deleted_at": None,
    }
    await database.program_purchases.insert_one(purchase_doc)

    await database.activity_log.insert_one(
        {
            "id": str(uuid.uuid4()),
            "actor_membership_id": current["membership_id"],
            "action": "dummy.mark_paid",
            "target": body.program_id,
            "meta": {"program_name": program.get("name"), "invoice_number": invoice_number},
            "created_at": _now_iso(),
        }
    )

    return {
        "success": True,
        "purchase_id": purchase_doc["id"],
        "invoice_number": invoice_number,
        "expiry_date": purchase_doc["expiry_date"],
        "program_id": body.program_id,
        "is_dummy": True,
    }



# ---------------- create order --------------------------------------------


@router.post("/order", response_model=CreateOrderResponse, status_code=201)
async def create_order(
    body: CreateOrderRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    program = await database.programs.find_one(
        {"id": body.program_id, "deleted_at": None, "is_active": True}
    )
    if not program:
        raise HTTPException(404, "Program not found")

    # Existing active access? Do not create another order.
    active = await get_active_purchase(database, current["membership_id"], body.program_id)
    if active:
        raise HTTPException(409, "You already have active access to this program.")

    # Sequence gate for non-subscription programs
    allowed, reason = await check_purchase_allowed(database, current["membership_id"], program)
    if not allowed:
        raise HTTPException(403, reason)

    # Per-program payment mode: block Razorpay order if program is manual_qr-only.
    from app.routes.manual_payments import _resolve_program_payment_mode
    prog_mode = await _resolve_program_payment_mode(database, program)
    if prog_mode == "manual_qr":
        raise HTTPException(
            409,
            "This program only accepts manual QR payment. Please use the QR flow.",
        )

    breakdown = await _compute_breakdown(database, program)
    amount_paise = int(round(breakdown["total"] * 100))
    if amount_paise <= 0:
        raise HTTPException(400, "Program is free — nothing to pay.")

    receipt = f"rw_{uuid.uuid4().hex[:12]}"[:40]
    notes = {
        "user_membership_id": current["membership_id"],
        "program_id": body.program_id,
        "program_name": program.get("name", "")[:80],
    }
    rzp_order = rzp_create_order(amount_paise=amount_paise, receipt=receipt, notes=notes)

    order_doc = {
        "id": str(uuid.uuid4()),
        "order_id": rzp_order["id"],
        "user_membership_id": current["membership_id"],
        "program_id": body.program_id,
        "amount_paise": amount_paise,
        "amount_rupees": breakdown["total"],
        "currency": "INR",
        "receipt": receipt,
        "status": "created",
        "breakdown": breakdown,
        "notes": notes,
        "is_mock": bool(rzp_order.get("is_mock", rzp_is_mock())),
        "razorpay_payment_id": None,
        "razorpay_signature": None,
        "verified_at": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "deleted_at": None,
    }
    await database.payment_orders.insert_one(order_doc)

    return CreateOrderResponse(
        order_id=rzp_order["id"],
        amount_paise=amount_paise,
        amount_rupees=breakdown["total"],
        currency="INR",
        receipt=receipt,
        key_id=key_id_for_frontend(),
        is_mock=order_doc["is_mock"],
        program={
            "id": program["id"],
            "name": program.get("name"),
            "thumbnail_url": program.get("thumbnail_url"),
            "validity_days": program.get("validity_days"),
        },
        breakdown=breakdown,
        prefill={
            "name": current.get("full_name", ""),
            "contact": current.get("mobile", ""),
        },
        notes=notes,
    )


# ---------------- verify payment ------------------------------------------


@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(
    body: VerifyPaymentRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    order = await database.payment_orders.find_one(
        {"order_id": body.razorpay_order_id, "deleted_at": None}
    )
    if not order:
        raise HTTPException(404, "Order not found")
    if order["user_membership_id"] != current["membership_id"]:
        raise HTTPException(403, "Order does not belong to current user")
    if order["status"] == "paid":
        # Idempotent — return existing purchase.
        purchase = await database.program_purchases.find_one({"payment_order_id": order["id"], "deleted_at": None})
        if purchase:
            return VerifyPaymentResponse(
                success=True,
                purchase_id=purchase["id"],
                invoice_number=purchase["invoice_number"],
                expiry_date=purchase["expiry_date"],
                amount=float(purchase.get("total", 0)),
                program_id=purchase["program_id"],
            )

    ok = verify_signature(body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature)
    if not ok:
        await database.payment_orders.update_one(
            {"_id": order["_id"]},
            {"$set": {"status": "signature_failed", "updated_at": _now_iso()}},
        )
        # Notify user that Razorpay verification failed
        try:
            from app.services.notify import payment_failed as _notify_fail
            program_hint = await database.programs.find_one(
                {"id": order["program_id"]}, {"name": 1}
            ) or {}
            await _notify_fail(
                database,
                membership_id=current["membership_id"],
                program_name=program_hint.get("name", "your program"),
                reason="Signature verification failed.",
            )
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(400, "Invalid Razorpay signature")

    program = await database.programs.find_one({"id": order["program_id"], "deleted_at": None})
    if not program:
        raise HTTPException(404, "Program disappeared")

    # ----- create the purchase row (activates program access) ---------
    now = datetime.now(timezone.utc)
    expiry = compute_expiry(now, int(program.get("validity_days") or 365))
    breakdown = order["breakdown"]
    invoice_number = f"INV-{uuid.uuid4().hex[:12].upper()}"

    purchase_doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": current["membership_id"],
        "program_id": order["program_id"],
        "payment_order_id": order["id"],
        "razorpay_order_id": order["order_id"],
        "razorpay_payment_id": body.razorpay_payment_id,
        "price_paid": breakdown["price"],
        "discount": breakdown["discount"],
        "taxable_amount": breakdown["taxable"],
        "gst_percent": breakdown["gst_percent"],
        "gst_amount": breakdown["gst_amount"],
        "total": breakdown["total"],
        "invoice_number": invoice_number,
        "purchase_date": now.isoformat(),
        "expiry_date": expiry.isoformat(),
        "renewal_date": None,
        "status": "active",
        "payment_status": "captured",
        "source": "razorpay",
        "is_mock": bool(order.get("is_mock", False)),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "deleted_at": None,
    }
    await database.program_purchases.insert_one(purchase_doc)

    # ----- mark order paid --------------------------------------------
    await database.payment_orders.update_one(
        {"_id": order["_id"]},
        {
            "$set": {
                "status": "paid",
                "razorpay_payment_id": body.razorpay_payment_id,
                "razorpay_signature": body.razorpay_signature,
                "verified_at": _now_iso(),
                "purchase_id": purchase_doc["id"],
                "updated_at": _now_iso(),
            }
        },
    )

    # ----- generate invoice PDF ---------------------------------------
    try:
        user = await database.users.find_one({"membership_id": current["membership_id"], "deleted_at": None}) or {}
        company_gst = await _get_setting(database, "company_gst_number", "")
        generate_invoice_pdf(purchase=purchase_doc, program=program, user=user, company_gst_number=company_gst)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Invoice PDF generation failed: %s", exc)

    # ----- Phase 6: 3-level referral commissions ---------------------
    try:
        await create_commissions_for_purchase(database, purchase_doc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Commission engine failed: %s", exc)

    # ----- Notification: payment success -----------------------------
    try:
        from app.services.notify import payment_success as _notify_success
        await _notify_success(
            database,
            membership_id=current["membership_id"],
            program_name=program.get("name", "your program"),
            amount=float(purchase_doc["total"]),
            source="razorpay",
        )
    except Exception:  # noqa: BLE001
        pass

    # ----- audit log --------------------------------------------------
    await database.activity_log.insert_one(
        {
            "id": str(uuid.uuid4()),
            "actor_membership_id": current["membership_id"],
            "action": "payment.verified",
            "target": order["order_id"],
            "meta": {"program_id": order["program_id"], "amount": breakdown["total"]},
            "created_at": _now_iso(),
        }
    )

    return VerifyPaymentResponse(
        success=True,
        purchase_id=purchase_doc["id"],
        invoice_number=invoice_number,
        expiry_date=purchase_doc["expiry_date"],
        amount=purchase_doc["total"],
        program_id=purchase_doc["program_id"],
    )


# ---------------------------------------------------------------------------
# Reconciliation — for the Razorpay UPI checkout race where Checkout.js shows
# "Payment Failed" to the user even though the payment succeeded on
# Razorpay's servers (money debited, webhook fires). Frontend calls this
# endpoint after Checkout closes to ask Razorpay's authoritative API for
# the true order status.
# ---------------------------------------------------------------------------

async def _complete_purchase_from_paid_order(
    database, order: dict, razorpay_payment_id: str,
    razorpay_signature: str | None = None, actor_id: str | None = None,
) -> dict:
    """Idempotently create a purchase row from a Razorpay order that has
    been confirmed paid (either via /verify signature check OR via
    /reconcile-order fetch OR via `payment.captured` webhook). Returns
    the purchase document (existing or newly created)."""
    # Idempotent — if purchase already exists for this order, return it.
    existing = await database.program_purchases.find_one(
        {"payment_order_id": order["id"], "deleted_at": None}
    )
    if existing:
        return existing
    # Race-safe fallback in case only razorpay_payment_id is present.
    if razorpay_payment_id:
        rp_dup = await database.program_purchases.find_one(
            {"razorpay_payment_id": razorpay_payment_id, "deleted_at": None}
        )
        if rp_dup:
            return rp_dup

    program = await database.programs.find_one({"id": order["program_id"], "deleted_at": None})
    if not program:
        raise HTTPException(404, "Program disappeared")
    now = datetime.now(timezone.utc)
    expiry = compute_expiry(now, int(program.get("validity_days") or 365))
    breakdown = order["breakdown"]
    invoice_number = f"INV-{uuid.uuid4().hex[:12].upper()}"

    purchase_doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": order["user_membership_id"],
        "program_id": order["program_id"],
        "payment_order_id": order["id"],
        "razorpay_order_id": order["order_id"],
        "razorpay_payment_id": razorpay_payment_id,
        "price_paid": breakdown["price"],
        "discount": breakdown["discount"],
        "taxable_amount": breakdown["taxable"],
        "gst_percent": breakdown["gst_percent"],
        "gst_amount": breakdown["gst_amount"],
        "total": breakdown["total"],
        "invoice_number": invoice_number,
        "purchase_date": now.isoformat(),
        "expiry_date": expiry.isoformat(),
        "renewal_date": None,
        "status": "active",
        "payment_status": "captured",
        "source": "razorpay",
        "is_mock": bool(order.get("is_mock", False)),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "deleted_at": None,
    }
    await database.program_purchases.insert_one(purchase_doc)

    await database.payment_orders.update_one(
        {"_id": order["_id"]},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": razorpay_payment_id,
            **({"razorpay_signature": razorpay_signature} if razorpay_signature else {}),
            "verified_at": _now_iso(),
            "purchase_id": purchase_doc["id"],
            "updated_at": _now_iso(),
        }},
    )

    # Invoice PDF (best-effort — never fail purchase completion on this).
    try:
        user = await database.users.find_one({"membership_id": order["user_membership_id"], "deleted_at": None}) or {}
        company_gst = await _get_setting(database, "company_gst_number", "")
        generate_invoice_pdf(purchase=purchase_doc, program=program, user=user, company_gst_number=company_gst)
    except Exception:  # noqa: BLE001
        logger.exception("Invoice PDF generation failed")

    # Commissions.
    try:
        await create_commissions_for_purchase(database, purchase_doc)
    except Exception:  # noqa: BLE001
        logger.exception("Commission engine failed")

    # Notification + audit.
    try:
        from app.services.notify import payment_success as _notify_success
        await _notify_success(
            database,
            membership_id=order["user_membership_id"],
            program_name=program.get("name", "your program"),
            amount=float(purchase_doc["total"]),
            source="razorpay",
        )
    except Exception:  # noqa: BLE001
        pass

    await database.activity_log.insert_one(
        {
            "id": str(uuid.uuid4()),
            "actor_membership_id": actor_id or order["user_membership_id"],
            "action": "payment.reconciled" if not razorpay_signature else "payment.verified",
            "target": order["order_id"],
            "meta": {"program_id": order["program_id"], "amount": breakdown["total"]},
            "created_at": _now_iso(),
        }
    )
    return purchase_doc


class ReconcileOrderRequest(BaseModel):
    razorpay_order_id: str = Field(..., min_length=1, max_length=64)


@router.post("/reconcile-order")
async def reconcile_order(
    body: ReconcileOrderRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Reconcile a Razorpay order against their authoritative API.

    Called by the frontend after Checkout closes (either via `handler` or
    `ondismiss`). Handles the well-known UPI race where Razorpay Checkout
    shows "Payment Failed" while the payment actually succeeded.

    - If Razorpay says the order is `paid`, we look up the captured
      payment and complete the purchase idempotently — even if the
      signature-verify flow was never called.
    - If Razorpay says it's not yet paid, we return the current status so
      the frontend can decide whether to keep polling.
    """
    order = await database.payment_orders.find_one(
        {"order_id": body.razorpay_order_id, "deleted_at": None}
    )
    if not order:
        raise HTTPException(404, "Order not found")
    if order["user_membership_id"] != current["membership_id"]:
        raise HTTPException(403, "Order does not belong to current user")

    # Fast-path: already completed.
    if order.get("status") == "paid":
        purchase = await database.program_purchases.find_one({"payment_order_id": order["id"], "deleted_at": None})
        return {
            "status": "paid",
            "purchase_id": purchase["id"] if purchase else None,
            "razorpay_payment_id": order.get("razorpay_payment_id"),
        }

    # Ask Razorpay for the current authoritative state.
    from app.services import payment as _pay
    client = _pay._client()  # noqa: SLF001
    if client is None:
        # Mock mode — nothing to reconcile; report current local status.
        return {"status": order.get("status", "created"), "purchase_id": None}

    try:
        live_order = client.order.fetch(order["order_id"])
        payments = client.order.payments(order["order_id"]) or {}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Razorpay reconcile fetch failed: {exc}") from exc

    live_status = (live_order or {}).get("status")
    items = (payments or {}).get("items") or []
    captured = next((p for p in items if p.get("status") == "captured"), None)

    if live_status == "paid" and captured:
        purchase = await _complete_purchase_from_paid_order(
            database,
            order=order,
            razorpay_payment_id=captured["id"],
            actor_id=current["membership_id"],
        )
        return {
            "status": "paid",
            "purchase_id": purchase["id"],
            "razorpay_payment_id": captured["id"],
        }
    return {
        "status": live_status or order.get("status") or "created",
        "razorpay_payment_id": None,
    }


# ---------------- webhook -------------------------------------------------


@router.post("/webhook", response_model=WebhookAck)
async def razorpay_webhook(request: Request):
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    ok = verify_webhook_signature(raw, signature, secret)
    if not ok and not rzp_is_mock():
        raise HTTPException(400, "Invalid webhook signature")

    import json

    try:
        payload = json.loads(raw or b"{}")
    except Exception:
        payload = {}

    event = payload.get("event", "unknown")
    # Best-effort: log the event; primary source of truth is /verify.
    from app.db.mongo import get_db
    database = get_db()
    if database is not None:
        await database.activity_log.insert_one(
            {
                "id": str(uuid.uuid4()),
                "actor_membership_id": None,
                "action": f"razorpay.webhook.{event}",
                "target": (payload.get("payload", {}).get("payment", {}).get("entity", {}) or {}).get("id"),
                "meta": {"event": event},
                "created_at": _now_iso(),
            }
        )

        # ---- One-time payment auto-complete.
        # `payment.captured` and `order.paid` fire when Razorpay has debited
        # the user successfully. If Checkout.js showed a spurious "Payment
        # Failed" and never triggered /verify, this webhook is the only
        # authoritative path to grant program access. Idempotent via
        # _complete_purchase_from_paid_order().
        #
        # (Subscription-specific events — subscription.charged / .pending /
        # .halted / .cancelled — are no longer handled. Subscriptions are
        # now implemented as manual per-cycle one-time orders, so the
        # payment.captured branch below covers renewals too.)
        try:
            if event in ("payment.captured", "order.paid"):
                pay_entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
                order_entity = ((payload.get("payload") or {}).get("order") or {}).get("entity") or {}
                rp_order_id = pay_entity.get("order_id") or order_entity.get("id")
                rp_payment_id = pay_entity.get("id")
                if rp_order_id and rp_payment_id:
                    order_doc = await database.payment_orders.find_one(
                        {"order_id": rp_order_id, "deleted_at": None}
                    )
                    if order_doc and order_doc.get("status") != "paid":
                        try:
                            await _complete_purchase_from_paid_order(
                                database,
                                order=order_doc,
                                razorpay_payment_id=rp_payment_id,
                                actor_id=None,
                            )
                        except Exception:  # noqa: BLE001
                            import logging
                            logging.getLogger(__name__).exception("payment.captured completion failed")
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception("one-time webhook handler failed")

    return WebhookAck()


# Alias — Razorpay dashboard is often configured with
# `/api/payments/razorpay/webhook`. Delegate to the same handler so admins
# can freely choose either URL.
@router.post("/razorpay/webhook", response_model=WebhookAck, include_in_schema=False)
async def razorpay_webhook_alias(request: Request):
    return await razorpay_webhook(request)


# ---------------- user history --------------------------------------------


@router.get("/me")
async def my_payments(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    filters = {"user_membership_id": current["membership_id"], "deleted_at": None}
    cursor = database.program_purchases.find(filters).sort("purchase_date", -1)
    total = await database.program_purchases.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for doc in cursor.skip(skip).limit(page_size):
        doc.pop("_id", None)
        prog = await database.programs.find_one({"id": doc["program_id"], "deleted_at": None})
        if prog:
            prog.pop("_id", None)
        doc["program"] = {"id": prog["id"], "name": prog.get("name"), "thumbnail_url": prog.get("thumbnail_url")} if prog else None
        items.append(doc)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


@router.get("/invoice/{purchase_id}")
async def download_invoice(
    purchase_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    purchase = await database.program_purchases.find_one(
        {"id": purchase_id, "user_membership_id": current["membership_id"], "deleted_at": None}
    )
    if not purchase:
        raise HTTPException(404, "Invoice not found")
    path = INVOICE_DIR / f"{purchase['invoice_number']}.pdf"
    if not path.exists():
        program = await database.programs.find_one({"id": purchase["program_id"], "deleted_at": None}) or {}
        user = await database.users.find_one({"membership_id": purchase["user_membership_id"], "deleted_at": None}) or {}
        gst = await _get_setting(database, "company_gst_number", "")
        generate_invoice_pdf(purchase=purchase, program=program, user=user, company_gst_number=gst)
    if not path.exists():
        raise HTTPException(500, "Failed to render invoice")
    return FileResponse(str(path), media_type="application/pdf", filename=f"{purchase['invoice_number']}.pdf")


def _serve_invoice(database: AsyncIOMotorDatabase, purchase: dict) -> Response:
    """Kept for possible future admin download route."""
    path = INVOICE_DIR / f"{purchase['invoice_number']}.pdf"
    if not path.exists():
        raise HTTPException(500, "Invoice not yet generated")
    return FileResponse(str(path), media_type="application/pdf", filename=f"{purchase['invoice_number']}.pdf")


# ---------------- subscription ---------------------------------------------
# All subscription endpoints have been REMOVED as of 2026-07-21.
# Rationale: Razorpay AutoPay UPI mandates were unreliable (Checkout.js
# false-negatives, dropped mandate authorization, orphaned mandates on
# retry). Subscriptions are now implemented as manual per-cycle one-time
# orders — the same `/payments/order` + `/payments/verify` flow used for
# one-off purchases. Program.validity_days is set to the cycle length
# (30 / 180 / 365) so a paid purchase expires exactly when renewal is due.


# ---------------- admin ---------------------------------------------------


@router.get("/admin/transactions", response_model=PaginatedResponse)
async def admin_list_transactions(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    q: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    filters: dict[str, Any] = {"deleted_at": None}
    if status_filter:
        filters["status"] = status_filter
    if q:
        filters["$or"] = [
            {"invoice_number": {"$regex": q, "$options": "i"}},
            {"user_membership_id": {"$regex": q, "$options": "i"}},
            {"razorpay_order_id": {"$regex": q, "$options": "i"}},
        ]
    total = await database.program_purchases.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for doc in database.program_purchases.find(filters).sort("purchase_date", -1).skip(skip).limit(page_size):
        doc.pop("_id", None)
        u = await database.users.find_one({"membership_id": doc["user_membership_id"], "deleted_at": None})
        p = await database.programs.find_one({"id": doc["program_id"], "deleted_at": None})
        doc["user"] = {"membership_id": doc["user_membership_id"], "full_name": (u or {}).get("full_name"), "mobile": (u or {}).get("mobile")}
        doc["program"] = {"id": doc["program_id"], "name": (p or {}).get("name")}
        items.append(doc)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


@router.get("/admin/summary")
async def admin_payment_summary(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    pipeline = [
        {"$match": {"deleted_at": None}},
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "revenue": {"$sum": "$total"},
            }
        },
    ]
    buckets = {"active": {"count": 0, "revenue": 0}, "expired": {"count": 0, "revenue": 0},
               "cancelled": {"count": 0, "revenue": 0}, "refunded": {"count": 0, "revenue": 0}}
    async for row in database.program_purchases.aggregate(pipeline):
        buckets.setdefault(row["_id"] or "unknown", {"count": 0, "revenue": 0})
        buckets[row["_id"] or "unknown"] = {"count": row["count"], "revenue": round(row["revenue"] or 0, 2)}
    gross = round(sum(v["revenue"] for k, v in buckets.items() if k != "refunded"), 2)
    total_revenue = round(gross - buckets["refunded"]["revenue"], 2)
    total_txn = sum(v["count"] for v in buckets.values())
    return {
        "total_revenue": total_revenue,
        "total_transactions": total_txn,
        "buckets": buckets,
    }


@router.post("/admin/transactions/{purchase_id}/refund")
async def admin_refund(
    purchase_id: str,
    body: RefundRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    purchase = await database.program_purchases.find_one({"id": purchase_id, "deleted_at": None})
    if not purchase:
        raise HTTPException(404, "Transaction not found")
    if purchase.get("status") == "refunded":
        raise HTTPException(409, "Already refunded")
    if purchase.get("status") not in ("active", "expired"):
        raise HTTPException(409, f"Cannot refund a {purchase.get('status')} transaction")

    # Mock refund — real Razorpay refund would call client.payment.refund(pid, {amount})
    await database.program_purchases.update_one(
        {"_id": purchase["_id"]},
        {
            "$set": {
                "status": "refunded",
                "refund_reason": body.reason,
                "refunded_at": _now_iso(),
                "refunded_by": admin["mobile"],
                "updated_at": _now_iso(),
            }
        },
    )
    await database.activity_log.insert_one(
        {
            "id": str(uuid.uuid4()),
            "actor_membership_id": admin["mobile"],
            "action": "payment.refunded",
            "target": purchase["invoice_number"],
            "meta": {"reason": body.reason, "amount": purchase.get("total")},
            "created_at": _now_iso(),
        }
    )
    return {"success": True, "is_mock": True}


async def _read_payment_settings(database: AsyncIOMotorDatabase) -> dict:
    keys = ["default_gst_percent", "default_validity_days", "company_gst_number", "invoice_prefix"]
    out: dict[str, Any] = {}
    for k in keys:
        out[k] = await _get_setting(database, k, None)
    out.setdefault("default_gst_percent", settings.DEFAULT_GST_PERCENT)
    out.setdefault("default_validity_days", settings.DEFAULT_VALIDITY_DAYS)
    out.setdefault("invoice_prefix", "INV")
    return out


@router.get("/admin/settings")
async def admin_get_payment_settings(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    return await _read_payment_settings(database)


@router.put("/admin/settings")
async def admin_update_payment_settings(
    body: PaymentSettingsUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    now = _now_iso()
    updates = body.model_dump(exclude_none=True)
    for k, v in updates.items():
        await database.app_settings.update_one(
            {"key": k},
            {
                "$set": {"value": v, "updated_at": now},
                "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now, "deleted_at": None},
            },
            upsert=True,
        )
    return await _read_payment_settings(database)
