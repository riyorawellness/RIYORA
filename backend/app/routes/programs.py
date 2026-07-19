"""Programs — user list/get (active only), admin full CRUD + activate/deactivate.

Phase 4 additions:
  * GET  /programs/me/dashboard         — categorised (purchased/completed/expired/locked/available)
  * GET  /programs/me/continue-learning — resume card
  * GET  /programs/{id}/eligibility     — can I purchase? (sequence gate)
  * POST /programs/{id}/purchase        — record purchase intent (no payment yet)
  * GET  /programs/{id}/status          — my access, expiry, progress in one call
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid
from datetime import datetime, timezone

from app.core.deps import db, get_current_admin, get_current_user, get_current_user_or_admin
from app.models.phase2 import PaginatedResponse, ProgramCreate, ProgramUpdate
from app.models.phase4 import PurchaseIntentCreate
from app.repositories.base import BaseRepository
from app.services.program_engine import (
    categorise_programs,
    check_purchase_allowed,
    continue_learning,
    is_program_completed_with_certificate,
)
from app.services.validity import compute_expiry, get_active_purchase, mark_expired_purchases

router = APIRouter(prefix="/programs", tags=["Programs"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(
        database,
        "programs",
        ["name", "slug", "short_description", "description"],
        "order_index",
    )


@router.get("", response_model=PaginatedResponse)
async def list_programs(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user_or_admin),
    search: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    is_subscription: bool | None = Query(default=None),
    is_featured: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str = Query(default="order_index,-created_at"),
):
    filters = {}
    if category_id:
        filters["category_id"] = category_id
    # Only admins can see inactive/hidden programs. Regular users are
    # ALWAYS restricted to is_active=True regardless of the query param.
    if current.get("is_admin"):
        if is_active is not None:
            filters["is_active"] = is_active
    else:
        filters["is_active"] = True
    if is_subscription is not None:
        filters["is_subscription"] = is_subscription
    if is_featured is not None:
        filters["is_featured"] = is_featured
    return await _repo(database).list_paginated(filters, search, sort, page, page_size)


@router.get("/{program_id}")
async def get_program(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user_or_admin),
):
    doc = await _repo(database).get(program_id)
    if not doc:
        raise HTTPException(404, "Program not found")
    return doc


# ---------------------- Phase 4: engine endpoints (user) ------------------


@router.get("/me/dashboard")
async def my_dashboard(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    await mark_expired_purchases(database, current["membership_id"])
    buckets = await categorise_programs(database, current["membership_id"])
    return {
        "counts": {k: len(v) for k, v in buckets.items()},
        **buckets,
    }


@router.get("/me/continue-learning")
async def my_continue(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    await mark_expired_purchases(database, current["membership_id"])
    return await continue_learning(database, current["membership_id"])


@router.get("/{program_id}/eligibility")
async def eligibility(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    program = await database.programs.find_one({"id": program_id, "deleted_at": None})
    if not program:
        raise HTTPException(404, "Program not found")
    allowed, reason = await check_purchase_allowed(database, current["membership_id"], program)
    already = await is_program_completed_with_certificate(database, current["membership_id"], program_id)
    active = await get_active_purchase(database, current["membership_id"], program_id)
    return {
        "eligible": allowed,
        "reason": reason if not allowed else None,
        "already_completed": already,
        "has_active_access": bool(active),
    }


@router.get("/{program_id}/status")
async def program_status(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    await mark_expired_purchases(database, current["membership_id"])
    program = await database.programs.find_one({"id": program_id, "deleted_at": None})
    if not program:
        raise HTTPException(404, "Program not found")
    program.pop("_id", None)
    active = await get_active_purchase(database, current["membership_id"], program_id)
    # Free-program enrolment counts as access even without a purchase row.
    enrolment = None
    if program.get("payment_type") == "free":
        enrolment = await database.program_enrolments.find_one(
            {"user_membership_id": current["membership_id"], "program_id": program_id, "deleted_at": None}
        )
        if enrolment:
            enrolment.pop("_id", None)
    # Active subscription mandate → user has access only when Razorpay has
    # actually charged at least once (status='active' or charges_count>0).
    # `authenticated` alone (mandate approved but no charge yet) MUST NOT
    # unlock the program — user must pay first.
    active_subscription = None
    if program.get("payment_type") == "subscription":
        active_subscription = await database.subscriptions.find_one({
            "user_membership_id": current["membership_id"],
            "program_id": program_id,
            "$or": [
                {"status": "active"},
                {"charges_count": {"$gt": 0}},
            ],
            "deleted_at": None,
        })
        if active_subscription:
            active_subscription.pop("_id", None)
    has_access = bool(active) or bool(enrolment) or bool(active_subscription)
    prog = await database.program_progress.find_one(
        {"user_membership_id": current["membership_id"], "program_id": program_id, "deleted_at": None}
    )
    cert = await database.certificates.find_one(
        {
            "user_membership_id": current["membership_id"],
            "program_id": program_id,
            "status": "issued",
            "deleted_at": None,
        }
    )
    if prog:
        prog.pop("_id", None)
    if cert:
        cert.pop("_id", None)
    # Include eligibility so the UI can hide the "Purchase" button when the
    # user hasn't completed the previous level yet (Level-gate rule).
    allowed, reason = await check_purchase_allowed(database, current["membership_id"], program)
    return {
        "program": program,
        "active_purchase": active,
        "enrolment": enrolment,
        "active_subscription": active_subscription,
        "has_access": has_access,
        "progress": prog,
        "certificate": cert,
        "eligibility": {
            "eligible": allowed,
            "reason": reason if not allowed else None,
        },
    }


@router.post("/{program_id}/purchase", status_code=201)
async def purchase_program(
    program_id: str,
    body: PurchaseIntentCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    program = await database.programs.find_one({"id": program_id, "deleted_at": None, "is_active": True})
    if not program:
        raise HTTPException(404, "Program not found")

    allowed, reason = await check_purchase_allowed(database, current["membership_id"], program)
    if not allowed:
        raise HTTPException(403, reason)

    now = datetime.now(timezone.utc)
    expiry = compute_expiry(now, int(program.get("validity_days", 365)))
    invoice = f"INV-{uuid.uuid4().hex[:12].upper()}"
    doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": current["membership_id"],
        "program_id": program_id,
        "price_paid": float(body.price_paid or program.get("price", 0)),
        "discount": float(body.discount or program.get("discount", 0)),
        "gst_amount": float(body.gst_amount or 0),
        "total": float(body.total or 0),
        "invoice_number": invoice,
        "purchase_date": now.isoformat(),
        "expiry_date": expiry.isoformat(),
        "renewal_date": None,
        "status": "active",
        "source": "user",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "deleted_at": None,
    }
    await database.program_purchases.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ------------------------- Admin ------------------------------------------
@router.post("/admin", status_code=201)
async def admin_create_program(
    body: ProgramCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    if body.category_id:
        cat = await database.program_categories.find_one({"id": body.category_id, "deleted_at": None})
        if not cat:
            raise HTTPException(400, "category_id does not exist")
    # Check for slug conflict — both live AND soft-deleted rows, because
    # the Mongo unique index doesn't filter by ``deleted_at``.
    existing = await database.programs.find_one({"slug": body.slug})
    if existing:
        if existing.get("deleted_at"):
            raise HTTPException(
                409,
                f"Slug '{body.slug}' was used by a previously deleted program. "
                "Pick a different slug (e.g. add a suffix).",
            )
        raise HTTPException(409, f"A program with slug '{body.slug}' already exists.")
    payload = body.model_dump()
    # ---- Keep the two representations consistent.
    # payment_type is the new source-of-truth; is_subscription stays in
    # sync with it so legacy queries keep working. Free programs are
    # forced to price=0 regardless of what the admin typed.
    pt = payload.get("payment_type", "one_time")
    payload["is_subscription"] = (pt == "subscription")
    if pt == "free":
        payload["price"] = 0
        payload["discount"] = 0
    if pt == "subscription" and not payload.get("subscription_frequency"):
        raise HTTPException(400, "Subscription programs require a subscription_frequency.")
    created = await _repo(database).create(payload, actor=admin["mobile"])
    # Broadcast to all users only if the program launches active + not admin-hidden.
    if created and created.get("is_active"):
        try:
            from app.services.notify import new_program_published as _notify_new
            await _notify_new(
                database,
                program_name=created.get("name", "a new program"),
                program_id=created["id"],
            )
        except Exception:  # noqa: BLE001
            pass
    return created


@router.put("/admin/{program_id}")
async def admin_update_program(
    program_id: str,
    body: ProgramUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updates = body.model_dump(exclude_none=True)
    if "category_id" in updates:
        cat = await database.program_categories.find_one({"id": updates["category_id"], "deleted_at": None})
        if not cat:
            raise HTTPException(400, "category_id does not exist")
    # Mirror payment_type ↔ is_subscription so legacy filters keep working.
    if "payment_type" in updates:
        pt = updates["payment_type"]
        updates["is_subscription"] = (pt == "subscription")
        if pt == "free":
            updates["price"] = 0
            updates["discount"] = 0
        if pt == "subscription" and not updates.get("subscription_frequency"):
            # Fall back to existing program's stored frequency; else reject.
            existing = await database.programs.find_one({"id": program_id})
            if not (existing and existing.get("subscription_frequency")):
                raise HTTPException(400, "Subscription programs require a subscription_frequency.")
    updated = await _repo(database).update(program_id, updates, actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Program not found")
    return updated


@router.post("/admin/{program_id}/activate")
async def admin_activate(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updated = await _repo(database).update(program_id, {"is_active": True}, actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Program not found")
    return updated


@router.post("/admin/{program_id}/deactivate")
async def admin_deactivate(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updated = await _repo(database).update(program_id, {"is_active": False}, actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Program not found")
    return updated


@router.delete("/admin/{program_id}")
async def admin_delete(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    ok = await _repo(database).soft_delete(program_id, actor=admin["mobile"])
    if not ok:
        raise HTTPException(404, "Program not found")
    return {"message": "Program deleted"}
