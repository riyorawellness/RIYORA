"""Payout Ledger — admin creates payout batches from approved commissions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import PaginatedResponse
from app.models.phase6 import PayoutCreate, PayoutMarkPaid

router = APIRouter(prefix="/payouts", tags=["Payouts"])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/me")
async def my_payouts(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    filters = {"user_membership_id": current["membership_id"], "deleted_at": None}
    total = await database.payouts.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for row in (
        database.payouts.find(filters).sort("created_at", -1).skip(skip).limit(page_size)
    ):
        row.pop("_id", None)
        items.append(row)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


# ---------------- admin --------------------------------------------------


@router.get("/admin", response_model=PaginatedResponse)
async def admin_list(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    status_filter: str | None = Query(default=None, alias="status"),
    user_membership_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    filters: dict = {"deleted_at": None}
    if status_filter:
        filters["status"] = status_filter
    if user_membership_id:
        filters["user_membership_id"] = user_membership_id
    total = await database.payouts.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for row in database.payouts.find(filters).sort("created_at", -1).skip(skip).limit(page_size):
        row.pop("_id", None)
        items.append(row)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


@router.get("/admin/pending-by-user")
async def admin_pending_by_user(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Aggregate approved commissions grouped by user — the admin's payout queue."""
    pipeline = [
        {"$match": {"status": "approved", "payout_id": None, "deleted_at": None}},
        {
            "$group": {
                "_id": "$sponsor_membership_id",
                "sponsor_name": {"$first": "$sponsor_name"},
                "amount": {"$sum": "$amount"},
                "count": {"$sum": 1},
                "ids": {"$push": "$id"},
            }
        },
        {"$sort": {"amount": -1}},
    ]
    items = []
    async for r in database.commissions.aggregate(pipeline):
        # Fetch bank details for convenience.
        bank = await database.bank_details.find_one(
            {"user_membership_id": r["_id"], "deleted_at": None}
        )
        if bank:
            bank.pop("_id", None)
        items.append(
            {
                "user_membership_id": r["_id"],
                "sponsor_name": r["sponsor_name"],
                "amount": round(r["amount"] or 0, 2),
                "commission_count": r["count"],
                "commission_ids": r["ids"],
                "bank_details": bank,
            }
        )
    return {"items": items, "count": len(items)}


@router.post("/admin", status_code=201)
async def admin_create_payout(
    body: PayoutCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    # Validate commissions
    rows = []
    async for r in database.commissions.find(
        {
            "id": {"$in": body.commission_ids},
            "sponsor_membership_id": body.user_membership_id,
            "deleted_at": None,
        }
    ):
        r.pop("_id", None)
        rows.append(r)
    if len(rows) != len(body.commission_ids):
        raise HTTPException(400, "One or more commission ids invalid or not owned by user")
    if any(r["status"] != "approved" or r.get("payout_id") for r in rows):
        raise HTTPException(400, "All commissions must be status='approved' and not already in a payout")

    total = round(sum(r["amount"] for r in rows), 2)
    now = _iso()
    doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": body.user_membership_id,
        "amount": total,
        "method": body.method,
        "reference": body.reference,
        "notes": body.notes,
        "status": "pending",
        "commission_ids": body.commission_ids,
        "created_at": now,
        "updated_at": now,
        "created_by": admin["mobile"],
        "paid_at": None,
        "deleted_at": None,
    }
    await database.payouts.insert_one(doc)
    await database.commissions.update_many(
        {"id": {"$in": body.commission_ids}},
        {"$set": {"payout_id": doc["id"], "updated_at": now}},
    )
    doc.pop("_id", None)
    return doc


@router.post("/admin/{payout_id}/mark-paid")
async def admin_mark_paid(
    payout_id: str,
    body: PayoutMarkPaid,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    payout = await database.payouts.find_one({"id": payout_id, "deleted_at": None})
    if not payout:
        raise HTTPException(404, "Payout not found")
    if payout["status"] == "paid":
        raise HTTPException(409, "Already paid")
    now = _iso()
    await database.payouts.update_one(
        {"_id": payout["_id"]},
        {
            "$set": {
                "status": "paid",
                "reference": body.reference,
                "notes": body.notes,
                "paid_at": now,
                "paid_by": admin["mobile"],
                "updated_at": now,
            }
        },
    )
    await database.commissions.update_many(
        {"id": {"$in": payout["commission_ids"]}},
        {"$set": {"status": "paid", "paid_at": now, "updated_at": now}},
    )
    return {"success": True, "id": payout_id, "status": "paid"}


@router.post("/admin/{payout_id}/cancel")
async def admin_cancel(
    payout_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    payout = await database.payouts.find_one({"id": payout_id, "deleted_at": None})
    if not payout:
        raise HTTPException(404, "Payout not found")
    if payout["status"] == "paid":
        raise HTTPException(409, "Cannot cancel a paid payout")
    now = _iso()
    await database.payouts.update_one(
        {"_id": payout["_id"]},
        {"$set": {"status": "cancelled", "cancelled_at": now, "updated_at": now}},
    )
    await database.commissions.update_many(
        {"id": {"$in": payout["commission_ids"]}},
        {"$set": {"payout_id": None, "updated_at": now}},
    )
    return {"success": True, "id": payout_id, "status": "cancelled"}
