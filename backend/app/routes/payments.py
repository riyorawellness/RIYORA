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
from fastapi.responses import FileResponse, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import PaginatedResponse
from app.models.phase5 import (
    CreateOrderRequest,
    CreateOrderResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
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
    create_subscription_mock,
    is_mock as rzp_is_mock,
    key_id_for_frontend,
    verify_signature,
    verify_webhook_signature,
)
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
    database = request.app.state.db if hasattr(request.app.state, "db") else None
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
    return WebhookAck()


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


# ---------------- subscription (mock only) --------------------------------


@router.post("/subscription", response_model=CreateSubscriptionResponse, status_code=201)
async def create_subscription(
    body: CreateSubscriptionRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    program = await database.programs.find_one(
        {"id": body.program_id, "deleted_at": None, "is_active": True, "is_subscription": True}
    )
    if not program:
        raise HTTPException(404, "Subscription program not found")

    sub = create_subscription_mock(program["id"], body.plan)
    now = datetime.now(timezone.utc)
    validity = int(program.get("validity_days") or 30)
    doc = {
        "id": str(uuid.uuid4()),
        "subscription_id": sub["id"],
        "user_membership_id": current["membership_id"],
        "program_id": program["id"],
        "plan": body.plan,
        "status": "active",
        "started_at": now.isoformat(),
        "next_charge_at": compute_expiry(now, validity).isoformat(),
        "is_mock": True,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "deleted_at": None,
    }
    await database.subscriptions.insert_one(doc)

    # Auto-create an active purchase so program is unlocked for the cycle.
    invoice_number = f"SUB-{uuid.uuid4().hex[:10].upper()}"
    breakdown = await _compute_breakdown(database, program)
    purchase_doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": current["membership_id"],
        "program_id": program["id"],
        "subscription_id": doc["id"],
        "razorpay_order_id": None,
        "razorpay_payment_id": sub["id"],
        "price_paid": breakdown["price"],
        "discount": breakdown["discount"],
        "taxable_amount": breakdown["taxable"],
        "gst_percent": breakdown["gst_percent"],
        "gst_amount": breakdown["gst_amount"],
        "total": breakdown["total"],
        "invoice_number": invoice_number,
        "purchase_date": now.isoformat(),
        "expiry_date": doc["next_charge_at"],
        "renewal_date": doc["next_charge_at"],
        "status": "active",
        "payment_status": "captured",
        "source": "subscription_mock",
        "is_mock": True,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "deleted_at": None,
    }
    await database.program_purchases.insert_one(purchase_doc)

    return CreateSubscriptionResponse(
        subscription_id=sub["id"],
        status="active",
        plan=body.plan,
        next_charge_at=doc["next_charge_at"],
        program={"id": program["id"], "name": program.get("name")},
        is_mock=True,
    )


@router.get("/subscription/me")
async def my_subscriptions(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    items = []
    async for s in database.subscriptions.find(
        {"user_membership_id": current["membership_id"], "deleted_at": None}
    ).sort("created_at", -1):
        s.pop("_id", None)
        items.append(s)
    return {"items": items}


@router.post("/subscription/{sub_id}/cancel")
async def cancel_subscription(
    sub_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    sub = await database.subscriptions.find_one(
        {"id": sub_id, "user_membership_id": current["membership_id"], "deleted_at": None}
    )
    if not sub:
        raise HTTPException(404, "Subscription not found")
    await database.subscriptions.update_one(
        {"_id": sub["_id"]},
        {"$set": {"status": "cancelled", "updated_at": _now_iso()}},
    )
    return {"success": True}


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
        buckets[row["_id"]] = {"count": row["count"], "revenue": round(row["revenue"] or 0, 2)}
    total_revenue = round(sum(v["revenue"] for k, v in buckets.items() if k != "refunded") - buckets["refunded"]["revenue"], 2)
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


@router.get("/admin/settings")
async def admin_get_payment_settings(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    keys = ["default_gst_percent", "default_validity_days", "company_gst_number", "invoice_prefix"]
    out = {}
    for k in keys:
        out[k] = await _get_setting(database, k, None)
    out.setdefault("default_gst_percent", settings.DEFAULT_GST_PERCENT)
    out.setdefault("default_validity_days", settings.DEFAULT_VALIDITY_DAYS)
    out.setdefault("invoice_prefix", "INV")
    return out


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
    return await admin_get_payment_settings(database, {})  # type: ignore[arg-type]
