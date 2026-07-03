"""Commission Ledger routes — user (read-only) + admin (approve/reject)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import PaginatedResponse
from app.models.phase6 import CommissionAdminAction
from app.services.commission_engine import summarise_user

router = APIRouter(prefix="/commissions", tags=["Commissions"])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/me/summary")
async def my_summary(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    return await summarise_user(database, current["membership_id"])


@router.get("/me")
async def my_commissions(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    level: Optional[int] = Query(default=None, ge=1, le=3),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    filters = {"sponsor_membership_id": current["membership_id"], "deleted_at": None}
    if status_filter:
        filters["status"] = status_filter
    if level:
        filters["level"] = level
    total = await database.commissions.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for row in (
        database.commissions.find(filters).sort("created_at", -1).skip(skip).limit(page_size)
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


# --------------- Admin --------------------------------------------------


@router.get("/admin", response_model=PaginatedResponse)
async def admin_list(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    q: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    sponsor_membership_id: Optional[str] = Query(default=None),
    level: Optional[int] = Query(default=None, ge=1, le=3),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    filters: dict = {"deleted_at": None}
    if status_filter:
        filters["status"] = status_filter
    if sponsor_membership_id:
        filters["sponsor_membership_id"] = sponsor_membership_id
    if level:
        filters["level"] = level
    if q:
        filters["$or"] = [
            {"buyer_membership_id": {"$regex": q, "$options": "i"}},
            {"sponsor_membership_id": {"$regex": q, "$options": "i"}},
            {"buyer_name": {"$regex": q, "$options": "i"}},
            {"sponsor_name": {"$regex": q, "$options": "i"}},
        ]
    total = await database.commissions.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for row in (
        database.commissions.find(filters).sort("created_at", -1).skip(skip).limit(page_size)
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


@router.get("/admin/summary")
async def admin_summary(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    pipeline = [
        {"$match": {"deleted_at": None}},
        {"$group": {"_id": "$status", "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    buckets = {
        "pending": {"amount": 0, "count": 0},
        "approved": {"amount": 0, "count": 0},
        "paid": {"amount": 0, "count": 0},
        "rejected": {"amount": 0, "count": 0},
    }
    async for r in database.commissions.aggregate(pipeline):
        buckets.setdefault(r["_id"], {"amount": 0, "count": 0})
        buckets[r["_id"]] = {
            "amount": round(r["amount"] or 0, 2),
            "count": r["count"],
        }
    payable = buckets["approved"]["amount"]
    total_earned = round(
        sum(buckets[s]["amount"] for s in ("pending", "approved", "paid")), 2
    )
    return {"buckets": buckets, "payable_now": payable, "total_earned": total_earned}


@router.post("/admin/{commission_id}/approve")
async def admin_approve(
    commission_id: str,
    body: CommissionAdminAction,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    row = await database.commissions.find_one({"id": commission_id, "deleted_at": None})
    if not row:
        raise HTTPException(404, "Commission not found")
    if row["status"] not in ("pending",):
        raise HTTPException(409, f"Cannot approve a {row['status']} commission")
    now = _iso()
    await database.commissions.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "status": "approved",
                "approved_at": now,
                "approved_by": admin["mobile"],
                "reason": body.reason,
                "updated_at": now,
            }
        },
    )
    return {"success": True, "id": commission_id, "status": "approved"}


@router.post("/admin/{commission_id}/reject")
async def admin_reject(
    commission_id: str,
    body: CommissionAdminAction,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    row = await database.commissions.find_one({"id": commission_id, "deleted_at": None})
    if not row:
        raise HTTPException(404, "Commission not found")
    if row["status"] == "paid":
        raise HTTPException(409, "Cannot reject a paid commission")
    now = _iso()
    await database.commissions.update_one(
        {"_id": row["_id"]},
        {
            "$set": {
                "status": "rejected",
                "rejected_at": now,
                "rejected_by": admin["mobile"],
                "reason": body.reason or "Rejected by admin",
                "updated_at": now,
            }
        },
    )
    return {"success": True, "id": commission_id, "status": "rejected"}


@router.post("/admin/bulk-approve")
async def admin_bulk_approve(
    body: dict,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    ids = body.get("ids") or []
    if not ids:
        raise HTTPException(400, "ids required")
    now = _iso()
    res = await database.commissions.update_many(
        {"id": {"$in": ids}, "status": "pending", "deleted_at": None},
        {
            "$set": {
                "status": "approved",
                "approved_at": now,
                "approved_by": admin["mobile"],
                "updated_at": now,
            }
        },
    )
    return {"approved": res.modified_count}
