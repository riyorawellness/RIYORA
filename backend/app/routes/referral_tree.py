"""Referral Tree — hierarchy read-only endpoints.

NOTE: NO commission calculation in this phase — only the tree/hierarchy.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import PaginatedResponse, ReferralTreeUpdate
from app.repositories.base import BaseRepository

router = APIRouter(prefix="/referral-tree", tags=["Referral Tree"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(database, "referral_tree", [], "level,joining_date")


async def _fetch_downline(
    database: AsyncIOMotorDatabase, root: str, max_depth: int = 3
) -> list[dict]:
    """Breadth-first fetch of downline up to max_depth levels."""
    result: list[dict] = []
    current_level = [root]
    depth = 0
    while current_level and depth < max_depth:
        cursor = database.referral_tree.find(
            {"sponsor_membership_id": {"$in": current_level}, "deleted_at": None}
        )
        next_level = []
        async for d in cursor:
            d.pop("_id", None)
            # Enrich with owner name from memberships collection.
            m = await database.memberships.find_one(
                {"membership_id": d["user_membership_id"]}, {"owner_name": 1}
            )
            d["owner_name"] = m.get("owner_name") if m else None
            d["depth_from_root"] = depth + 1
            result.append(d)
            next_level.append(d["user_membership_id"])
        current_level = next_level
        depth += 1
    return result


@router.get("/me")
async def my_tree(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    max_depth: int = Query(default=3, ge=1, le=10),
):
    downline = await _fetch_downline(database, current["membership_id"], max_depth)
    return {
        "root": {
            "membership_id": current["membership_id"],
            "owner_name": current["full_name"],
            "sponsor_membership_id": current["sponsor_membership_id"],
        },
        "downline": downline,
        "count_by_level": {
            f"L{i}": sum(1 for d in downline if d["depth_from_root"] == i)
            for i in range(1, max_depth + 1)
        },
        "total_downline": len(downline),
    }


@router.get("/me/upline")
async def my_upline(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    max_depth: int = Query(default=3, ge=1, le=10),
):
    chain = []
    sponsor_id = current["sponsor_membership_id"]
    depth = 0
    while sponsor_id and depth < max_depth:
        node = await database.referral_tree.find_one(
            {"user_membership_id": sponsor_id, "deleted_at": None}
        )
        if not node:
            break
        node.pop("_id", None)
        m = await database.memberships.find_one({"membership_id": sponsor_id}, {"owner_name": 1})
        node["owner_name"] = m.get("owner_name") if m else None
        node["depth_from_me"] = depth + 1
        chain.append(node)
        sponsor_id = node.get("sponsor_membership_id")
        depth += 1
    return {"upline": chain}


# ------------------------- Admin ------------------------------------------
@router.get("/admin", response_model=PaginatedResponse)
async def admin_list_tree(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    sponsor_membership_id: str | None = Query(default=None),
    level: int | None = Query(default=None, ge=0),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="level,joining_date"),
):
    filters = {}
    if sponsor_membership_id:
        filters["sponsor_membership_id"] = sponsor_membership_id
    if level is not None:
        filters["level"] = level
    if status:
        filters["status"] = status
    return await _repo(database).list_paginated(filters, None, sort, page, page_size)


@router.get("/admin/{membership_id}")
async def admin_get_tree(
    membership_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    max_depth: int = Query(default=3, ge=1, le=10),
):
    node = await database.referral_tree.find_one(
        {"user_membership_id": membership_id, "deleted_at": None}
    )
    if not node:
        raise HTTPException(404, "Member not found in referral tree")
    node.pop("_id", None)
    downline = await _fetch_downline(database, membership_id, max_depth)
    return {"root": node, "downline": downline, "total_downline": len(downline)}


@router.put("/admin/{membership_id}")
async def admin_update_tree(
    membership_id: str,
    body: ReferralTreeUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updates = body.model_dump(exclude_none=True)
    node = await database.referral_tree.find_one_and_update(
        {"user_membership_id": membership_id, "deleted_at": None},
        {"$set": {**updates, "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), "updated_by": admin["mobile"]}},
        return_document=True,
    )
    if not node:
        raise HTTPException(404, "Member not found in referral tree")
    node.pop("_id", None)
    return node
