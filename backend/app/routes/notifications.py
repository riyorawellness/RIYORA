"""Notifications — DB storage only (no sending / no push).

- User: list personal + broadcast notifications, mark read, unread count.
- Admin: CRUD any notification, list all, broadcast to all users.
"""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import (
    NotificationCreate,
    NotificationMarkRead,
    PaginatedResponse,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _clean(d: dict | None) -> dict | None:
    if d is None:
        return None
    d.pop("_id", None)
    return d


@router.get("/me", response_model=PaginatedResponse)
async def list_my_notifications(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    category: str | None = Query(default=None),
    is_read: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    # NOTE: Admin broadcast route (/admin/notifications) materialises one
    # notification row per user with ``user_membership_id`` set. So we
    # ONLY need to filter by ``user_membership_id`` here — adding an
    # ``is_broadcast: True`` OR clause would return every user's copy of
    # every broadcast, causing 99+ duplicates on the user's screen.
    query: dict = {
        "deleted_at": None,
        "user_membership_id": current["membership_id"],
    }
    if category:
        query["category"] = category
    if is_read is not None:
        query["is_read"] = is_read

    total = await database.notifications.count_documents(query)
    unread = await database.notifications.count_documents({**query, "is_read": False})
    cursor = (
        database.notifications.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    async for d in cursor:
        items.append(_clean(d))
    return {
        "items": items,
        "unread": unread,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/me/unread-count")
async def unread_count(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    n = await database.notifications.count_documents(
        {
            "deleted_at": None,
            "is_read": False,
            "user_membership_id": current["membership_id"],
        }
    )
    return {"unread": n}


@router.post("/me/read-all")
async def read_all(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Mark all notifications for this user as read.

    Broadcasts are materialised as per-user rows by the admin broadcast
    route, so we can safely flip ``is_read`` without leaking state across
    users.
    """
    result = await database.notifications.update_many(
        {
            "deleted_at": None,
            "is_read": False,
            "user_membership_id": current["membership_id"],
        },
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"success": True, "updated": result.modified_count}


@router.post("/me/mark-read")
async def mark_read(
    body: NotificationMarkRead,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Mark notifications as read by ID (personal or per-user broadcast rows)."""
    result = await database.notifications.update_many(
        {
            "id": {"$in": body.ids},
            "user_membership_id": current["membership_id"],
            "deleted_at": None,
        },
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"updated": result.modified_count}


# ------------------------- Admin ------------------------------------------
@router.get("/admin", response_model=PaginatedResponse)
async def admin_list(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    user_membership_id: str | None = Query(default=None),
    is_broadcast: bool | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    query: dict = {"deleted_at": None}
    if user_membership_id:
        query["user_membership_id"] = user_membership_id
    if is_broadcast is not None:
        query["is_broadcast"] = is_broadcast
    if category:
        query["category"] = category
    total = await database.notifications.count_documents(query)
    cursor = (
        database.notifications.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    async for d in cursor:
        items.append(_clean(d))
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("/admin", status_code=201)
async def admin_create(
    body: NotificationCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": body.user_membership_id,
        "is_broadcast": body.user_membership_id is None,
        "title": body.title,
        "body": body.body,
        "category": body.category,
        "meta": body.meta,
        "is_read": False,
        "read_at": None,
        "created_at": now,
        "created_by": admin["mobile"],
        "updated_at": now,
        "deleted_at": None,
    }
    await database.notifications.insert_one(doc)
    return _clean(doc)


@router.delete("/admin/{notification_id}")
async def admin_delete(
    notification_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    result = await database.notifications.update_one(
        {"id": notification_id, "deleted_at": None},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat(), "updated_by": admin["mobile"]}},
    )
    if result.modified_count == 0:
        raise HTTPException(404, "Notification not found")
    return {"message": "Notification deleted"}
