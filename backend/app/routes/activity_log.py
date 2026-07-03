"""Activity Log — read-only telemetry of user/admin actions.

Note: This is the general activity_log table (distinct from the existing
audit_log). Write is done internally by other endpoints; here we expose read
endpoints (admin only, plus a user endpoint to see their own log).
"""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import PaginatedResponse

router = APIRouter(prefix="/activity-log", tags=["Activity Log"])


async def write_activity(
    database: AsyncIOMotorDatabase,
    actor_membership_id: str | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    meta: dict | None = None,
) -> None:
    await database.activity_log.insert_one(
        {
            "id": str(uuid.uuid4()),
            "actor_membership_id": actor_membership_id,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "meta": meta or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def _clean(d: dict) -> dict:
    d.pop("_id", None)
    return d


@router.get("/me", response_model=PaginatedResponse)
async def my_activity(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    action: str | None = Query(default=None),
    entity: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    query: dict = {"actor_membership_id": current["membership_id"]}
    if action:
        query["action"] = action
    if entity:
        query["entity"] = entity
    total = await database.activity_log.count_documents(query)
    cursor = (
        database.activity_log.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_clean(d) async for d in cursor]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/admin", response_model=PaginatedResponse)
async def admin_list_activity(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    actor_membership_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    entity: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
):
    query: dict = {}
    if actor_membership_id:
        query["actor_membership_id"] = actor_membership_id
    if action:
        query["action"] = action
    if entity:
        query["entity"] = entity
    total = await database.activity_log.count_documents(query)
    cursor = (
        database.activity_log.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_clean(d) async for d in cursor]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
