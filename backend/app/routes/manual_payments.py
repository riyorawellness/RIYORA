"""Manual QR Payment Provider — Phase 11.

Endpoints:
    Public (user):
        GET   /api/payments/mode                 → current active payment mode
        GET   /api/payments/manual/qr            → active QR + company details for checkout
        GET   /api/payments/manual/quote         → server-computed breakdown for a program
        POST  /api/payments/manual/submit        → submit UTR + screenshot for a one-time program
        GET   /api/payments/manual/me            → my payment requests (history)
        GET   /api/payments/manual/pending       → my currently-pending requests (for Home card)

    Admin:
        GET   /api/admin/payments/settings       → payment mode + QR + bank details
        PUT   /api/admin/payments/settings       → update payment mode + QR + bank details
        POST  /api/admin/payments/qr             → upload new QR (multipart)
        DELETE/api/admin/payments/qr             → delete active QR image
        GET   /api/admin/payments/manual         → list requests with filters
        GET   /api/admin/payments/manual/summary → counts by status
        POST  /api/admin/payments/manual/{id}/action → approve / reject

Business rules:
    - Manual QR applies ONLY to one-time programs (is_subscription != True).
    - Inner Peace / subscription programs → 409 "coming soon".
    - Only one PENDING request per (user, program) at a time.
    - On approve → insert program_purchases row (source='manual_qr'), fire
      commissions, send notification, generate invoice.
    - On reject → keep locked, store reason, notify user.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, UploadFile,
)
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase11 import (
    ALLOWED_MODES, PaymentActionRequest, PaymentModeUpdate,
    PaymentSettingsUpsert, PaymentSubmitRequest,
)
from app.services.commission_engine import create_commissions_for_purchase
from app.services.invoice import generate_invoice_pdf
from app.services.program_engine import check_purchase_allowed
from app.services.validity import compute_expiry, get_active_purchase
from app.utils.audit import log_action
from app.utils.file_validator import validate_upload

logger = logging.getLogger(__name__)

user_router = APIRouter(prefix="/payments", tags=["Manual Payments"])
admin_router = APIRouter(prefix="/admin/payments", tags=["Admin Manual Payments"])


UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_setting(database: AsyncIOMotorDatabase, key: str, default=None):
    row = await database.app_settings.find_one({"key": key, "deleted_at": None})
    return (row or {}).get("value", default)


async def _set_setting(database: AsyncIOMotorDatabase, key: str, value):
    now = _now()
    await database.app_settings.update_one(
        {"key": key},
        {
            "$set": {"value": value, "updated_at": now},
            "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now, "deleted_at": None},
        },
        upsert=True,
    )


async def _payment_mode(database: AsyncIOMotorDatabase) -> str:
    mode = await _get_setting(database, "payment_mode", "manual_qr")
    return mode if mode in ALLOWED_MODES else "manual_qr"


async def _compute_breakdown(database: AsyncIOMotorDatabase, program: dict) -> dict:
    from app.routes.payments import _compute_breakdown as _rzp_compute
    return await _rzp_compute(database, program)


async def _notify(database: AsyncIOMotorDatabase, mid: str, title: str, body: str, category: str = "system") -> None:
    now = _now()
    await database.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_membership_id": mid,
        "title": title,
        "body": body,
        "category": category,
        "is_broadcast": False,
        "is_read": False,
        "cta_link": "/app/payment-history",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    })


# ============================================================================
# PUBLIC / USER
# ============================================================================


@user_router.get("/mode")
async def get_payment_mode(database: AsyncIOMotorDatabase = Depends(db)):
    return {"payment_mode": await _payment_mode(database)}


@user_router.get("/manual/qr")
async def get_public_qr(
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user),
):
    """Return the currently-active QR + company details for user checkout."""
    active = await database.payment_settings.find_one({"is_active": True, "deleted_at": None})
    if not active:
        raise HTTPException(503, "Manual payment is not configured yet. Please contact support.")
    active.pop("_id", None)
    return active


@user_router.get("/manual/quote")
async def get_quote(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Server-computed breakdown so the user can review before paying."""
    program = await database.programs.find_one(
        {"id": program_id, "deleted_at": None, "is_active": True}
    )
    if not program:
        raise HTTPException(404, "Program not found")
    if program.get("is_subscription"):
        raise HTTPException(409, "Inner Peace is coming soon with AutoPay — manual payment is not accepted for subscription programs.")

    active = await get_active_purchase(database, current["membership_id"], program_id)
    if active:
        raise HTTPException(409, "You already have active access to this program.")

    allowed, reason = await check_purchase_allowed(database, current["membership_id"], program)
    if not allowed:
        raise HTTPException(403, reason)

    pending = await database.payment_requests.find_one({
        "user_membership_id": current["membership_id"],
        "program_id": program_id,
        "status": "pending",
        "deleted_at": None,
    })

    return {
        "program": {
            "id": program["id"],
            "name": program.get("name"),
            "level": program.get("level"),
            "thumbnail_url": program.get("thumbnail_url"),
            "validity_days": program.get("validity_days"),
        },
        "breakdown": await _compute_breakdown(database, program),
        "pending_request": _clean(pending),
    }


def _clean(doc: dict | None) -> dict | None:
    if not doc:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


@user_router.post("/manual/submit", status_code=201)
async def submit_payment(
    body: PaymentSubmitRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    program = await database.programs.find_one(
        {"id": body.program_id, "deleted_at": None, "is_active": True}
    )
    if not program:
        raise HTTPException(404, "Program not found")
    if program.get("is_subscription"):
        raise HTTPException(409, "Manual payment not accepted for Inner Peace subscription.")

    if await get_active_purchase(database, current["membership_id"], body.program_id):
        raise HTTPException(409, "You already have active access to this program.")

    allowed, reason = await check_purchase_allowed(database, current["membership_id"], program)
    if not allowed:
        raise HTTPException(403, reason)

    existing_pending = await database.payment_requests.find_one({
        "user_membership_id": current["membership_id"],
        "program_id": body.program_id,
        "status": "pending",
        "deleted_at": None,
    })
    if existing_pending:
        raise HTTPException(409, "You already have a pending payment for this program. Please wait for admin verification.")

    breakdown = await _compute_breakdown(database, program)
    now = _now()
    req = {
        "id": str(uuid.uuid4()),
        "user_membership_id": current["membership_id"],
        "user_name": current.get("full_name"),
        "user_mobile": current.get("mobile"),
        "program_id": program["id"],
        "program_name": program.get("name"),
        "program_level": program.get("level"),
        "amount_paid": breakdown["total"],
        "price": breakdown["price"],
        "discount": breakdown["discount"],
        "taxable_amount": breakdown["taxable"],
        "gst_percent": breakdown["gst_percent"],
        "gst_amount": breakdown["gst_amount"],
        "total": breakdown["total"],
        "utr": body.utr,
        "transaction_date": body.transaction_date,
        "screenshot_url": body.screenshot_url,
        "remarks": body.remarks,
        "status": "pending",  # pending | approved | rejected
        "rejection_reason": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "purchase_id": None,
        "submitted_at": now,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "source": "manual_qr",
    }
    await database.payment_requests.insert_one(req)
    req.pop("_id", None)

    await _notify(
        database, current["membership_id"],
        title="Payment received",
        body=(
            f"We have received your payment of ₹{breakdown['total']:,.0f} for "
            f"{program.get('name')}. Our team will verify it shortly."
        ),
        category="payment",
    )
    await log_action(
        database, actor_id=current["membership_id"], action="payment.manual.submit",
        entity="payment_request", entity_id=req["id"],
        meta={"program_id": program["id"], "amount": breakdown["total"], "utr": body.utr},
    )
    return req


@user_router.post("/manual/upload-screenshot", status_code=201)
async def upload_screenshot(
    file: UploadFile = File(...),
    _current: dict = Depends(get_current_user),
):
    """User-facing screenshot upload — image only, ≤5 MB, magic-byte checked."""
    content = await validate_upload(file, kind="image")
    file_id = str(uuid.uuid4())
    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()[:8]
    stored = f"ss-{file_id}{ext}"
    (UPLOAD_DIR / stored).write_bytes(content)
    return {"url": f"/api/uploads/screenshot/{stored}", "size_bytes": len(content)}


@user_router.get("/manual/me")
async def my_payment_requests(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    filters: dict[str, Any] = {"user_membership_id": current["membership_id"], "deleted_at": None}
    if status_filter:
        filters["status"] = status_filter
    total = await database.payment_requests.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for r in database.payment_requests.find(filters).sort("submitted_at", -1).skip(skip).limit(page_size):
        r.pop("_id", None)
        items.append(r)
    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


@user_router.get("/manual/pending")
async def my_pending_payments(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """List used by the Home 'Payment verification pending' card."""
    items = []
    async for r in database.payment_requests.find({
        "user_membership_id": current["membership_id"],
        "status": "pending",
        "deleted_at": None,
    }).sort("submitted_at", -1):
        r.pop("_id", None)
        items.append(r)
    return {"items": items}


# ============================================================================
# ADMIN
# ============================================================================


@admin_router.get("/settings")
async def admin_get_settings(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    mode = await _payment_mode(database)
    row = await database.payment_settings.find_one({"is_active": True, "deleted_at": None})
    if row:
        row.pop("_id", None)
    return {"payment_mode": mode, "active_qr": row}


@admin_router.put("/settings")
async def admin_put_settings(
    body: PaymentSettingsUpsert,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    """Upsert the active payment_settings row + audit."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    now = _now()

    existing = await database.payment_settings.find_one({"is_active": True, "deleted_at": None})
    if existing:
        await database.payment_settings.update_one(
            {"_id": existing["_id"]},
            {"$set": {**updates, "updated_at": now, "updated_by": admin["mobile"]}},
        )
    else:
        doc = {
            "id": str(uuid.uuid4()),
            "company_name": None, "account_holder_name": None, "bank_name": None,
            "upi_id": None, "account_number": None, "ifsc": None,
            "qr_image_url": None, "payment_instructions": None,
            "is_active": True,
            **updates,
            "created_at": now,
            "updated_at": now,
            "updated_by": admin["mobile"],
            "deleted_at": None,
        }
        await database.payment_settings.insert_one(doc)

    await log_action(
        database, actor_id=admin["mobile"], action="payment.settings.update",
        entity="payment_settings", meta={"fields": list(updates.keys())},
    )
    return await admin_get_settings(database, admin)


@admin_router.put("/mode")
async def admin_set_payment_mode(
    body: PaymentModeUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    await _set_setting(database, "payment_mode", body.payment_mode)
    await log_action(
        database, actor_id=admin["mobile"], action="payment.mode.set",
        entity="payment_settings", meta={"payment_mode": body.payment_mode},
    )
    return {"payment_mode": body.payment_mode}


@admin_router.post("/qr", status_code=201)
async def admin_upload_qr(
    file: UploadFile = File(...),
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    """Upload a new QR image and mark it as the active QR."""
    content = await validate_upload(file, kind="image")
    file_id = str(uuid.uuid4())
    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()[:8]
    stored = f"qr-{file_id}{ext}"
    (UPLOAD_DIR / stored).write_bytes(content)
    url = f"/api/uploads/screenshot/{stored}"

    # Persist to active row (create one if missing).
    existing = await database.payment_settings.find_one({"is_active": True, "deleted_at": None})
    now = _now()
    if existing:
        await database.payment_settings.update_one(
            {"_id": existing["_id"]},
            {"$set": {"qr_image_url": url, "updated_at": now, "updated_by": admin["mobile"]}},
        )
    else:
        await database.payment_settings.insert_one({
            "id": str(uuid.uuid4()),
            "qr_image_url": url,
            "is_active": True,
            "created_at": now, "updated_at": now,
            "updated_by": admin["mobile"],
            "deleted_at": None,
        })
    await log_action(database, actor_id=admin["mobile"], action="payment.qr.upload", entity="payment_settings")
    return {"url": url}


@admin_router.delete("/qr")
async def admin_delete_qr(
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    existing = await database.payment_settings.find_one({"is_active": True, "deleted_at": None})
    if not existing:
        raise HTTPException(404, "No active QR to delete")
    await database.payment_settings.update_one(
        {"_id": existing["_id"]},
        {"$set": {"qr_image_url": None, "updated_at": _now(), "updated_by": admin["mobile"]}},
    )
    await log_action(database, actor_id=admin["mobile"], action="payment.qr.delete", entity="payment_settings")
    return {"success": True}


@admin_router.get("/manual/summary")
async def admin_manual_summary(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    pipeline = [
        {"$match": {"deleted_at": None}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "amount": {"$sum": "$total"}}},
    ]
    out = {"pending": {"count": 0, "amount": 0}, "approved": {"count": 0, "amount": 0}, "rejected": {"count": 0, "amount": 0}}
    async for r in database.payment_requests.aggregate(pipeline):
        out[r["_id"] or "unknown"] = {"count": r["count"], "amount": round(r["amount"] or 0, 2)}
    return out


@admin_router.get("/manual")
async def admin_list_manual(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    status_filter: str | None = Query(default="pending", alias="status"),
    q: str | None = Query(default=None),
    program_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    filters: dict[str, Any] = {"deleted_at": None}
    if status_filter and status_filter != "all":
        filters["status"] = status_filter
    if program_id:
        filters["program_id"] = program_id
    if since or until:
        rng = {}
        if since: rng["$gte"] = since
        if until: rng["$lte"] = until
        filters["submitted_at"] = rng
    if q:
        filters["$or"] = [
            {"utr": {"$regex": q, "$options": "i"}},
            {"user_membership_id": {"$regex": q, "$options": "i"}},
            {"user_name": {"$regex": q, "$options": "i"}},
        ]
    total = await database.payment_requests.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for r in database.payment_requests.find(filters).sort("submitted_at", -1).skip(skip).limit(page_size):
        r.pop("_id", None)
        items.append(r)
    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


@admin_router.post("/manual/{request_id}/action")
async def admin_action(
    request_id: str,
    body: PaymentActionRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    req = await database.payment_requests.find_one({"id": request_id, "deleted_at": None})
    if not req:
        raise HTTPException(404, "Payment request not found")
    if req["status"] != "pending":
        raise HTTPException(409, f"Request already {req['status']}")

    now = _now()

    if body.action == "reject":
        reason = body.rejection_reason or body.remarks or "Rejected by admin"
        await database.payment_requests.update_one(
            {"_id": req["_id"]},
            {"$set": {
                "status": "rejected",
                "rejection_reason": reason,
                "remarks": body.remarks or req.get("remarks"),
                "reviewed_by": admin["mobile"],
                "reviewed_at": now,
                "updated_at": now,
            }},
        )
        await _notify(
            database, req["user_membership_id"],
            title="Payment rejected",
            body=(
                f"Your payment for {req['program_name']} was not approved. Reason: "
                f"{reason}. You can submit a fresh payment from the program page."
            ),
            category="payment",
        )
        await log_action(
            database, actor_id=admin["mobile"], action="payment.manual.reject",
            entity="payment_request", entity_id=req["id"],
            meta={"reason": reason, "amount": req.get("total")},
        )
        return {"success": True, "status": "rejected"}

    # ---------- Approve ------------------------------------------------
    program = await database.programs.find_one({"id": req["program_id"], "deleted_at": None})
    if not program:
        raise HTTPException(404, "Program disappeared")

    now_dt = datetime.now(timezone.utc)
    expiry = compute_expiry(now_dt, int(program.get("validity_days") or 365))
    invoice_number = f"INV-M-{uuid.uuid4().hex[:10].upper()}"

    purchase_doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": req["user_membership_id"],
        "program_id": req["program_id"],
        "payment_request_id": req["id"],
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "utr": req["utr"],
        "price_paid": req["price"],
        "discount": req["discount"],
        "taxable_amount": req["taxable_amount"],
        "gst_percent": req["gst_percent"],
        "gst_amount": req["gst_amount"],
        "total": req["total"],
        "invoice_number": invoice_number,
        "purchase_date": now_dt.isoformat(),
        "expiry_date": expiry.isoformat(),
        "renewal_date": None,
        "status": "active",
        "payment_status": "captured",
        "source": "manual_qr",
        "is_mock": False,
        "created_at": now_dt.isoformat(),
        "updated_at": now_dt.isoformat(),
        "deleted_at": None,
    }
    await database.program_purchases.insert_one(purchase_doc)

    await database.payment_requests.update_one(
        {"_id": req["_id"]},
        {"$set": {
            "status": "approved",
            "purchase_id": purchase_doc["id"],
            "remarks": body.remarks or req.get("remarks"),
            "reviewed_by": admin["mobile"],
            "reviewed_at": now,
            "updated_at": now,
        }},
    )

    # Invoice PDF (best effort)
    try:
        user = await database.users.find_one({"membership_id": req["user_membership_id"], "deleted_at": None}) or {}
        gst = await _get_setting(database, "company_gst_number", "")
        generate_invoice_pdf(purchase=purchase_doc, program=program, user=user, company_gst_number=gst)
    except Exception:
        logger.exception("invoice generation failed for manual approval %s", req["id"])

    # 3-level referral commissions (identical to Razorpay flow)
    try:
        await create_commissions_for_purchase(database, purchase_doc)
    except Exception:
        logger.exception("commission engine failed for manual approval %s", req["id"])

    await _notify(
        database, req["user_membership_id"],
        title="Payment approved 🎉",
        body=(
            f"Your payment for {req['program_name']} has been verified. "
            f"The program is now unlocked and available in your library."
        ),
        category="payment",
    )
    await log_action(
        database, actor_id=admin["mobile"], action="payment.manual.approve",
        entity="payment_request", entity_id=req["id"],
        meta={"amount": req.get("total"), "purchase_id": purchase_doc["id"]},
    )
    return {"success": True, "status": "approved", "purchase_id": purchase_doc["id"]}


# ============================================================================
# Screenshot / QR image serving (uploaded by user OR admin)
# ============================================================================

serve_router = APIRouter(prefix="/uploads", tags=["Uploads"])


@serve_router.get("/screenshot/{filename}")
async def serve_upload(filename: str):
    """Serve QR / screenshot images. No auth by design — filenames are UUID-based."""
    from fastapi.responses import FileResponse
    # Basic path traversal guard
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(str(path))
