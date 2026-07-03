"""Settings — user_settings (per-user), app_settings (public+admin), system_configuration (admin)."""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import (
    AppSettingUpsert,
    PaginatedResponse,
    SystemConfigurationUpsert,
    UserSettingUpsert,
)

router = APIRouter(prefix="/settings", tags=["Settings"])


def _clean(d: dict | None) -> dict | None:
    if d is None:
        return None
    d.pop("_id", None)
    return d


# ------------------------- User Settings ---------------------------------
@router.get("/me")
async def list_my_settings(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    cursor = database.user_settings.find({"user_membership_id": current["membership_id"]})
    out = {}
    async for d in cursor:
        out[d["key"]] = d.get("value")
    return out


@router.put("/me")
async def upsert_my_setting(
    body: UserSettingUpsert,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc).isoformat()
    doc = await database.user_settings.find_one_and_update(
        {"user_membership_id": current["membership_id"], "key": body.key},
        {
            "$set": {"value": body.value, "updated_at": now},
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "user_membership_id": current["membership_id"],
                "key": body.key,
                "created_at": now,
            },
        },
        upsert=True,
        return_document=True,
    )
    return _clean(doc)


@router.delete("/me/{key}")
async def delete_my_setting(
    key: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    result = await database.user_settings.delete_one(
        {"user_membership_id": current["membership_id"], "key": key}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Setting not found")
    return {"message": "Setting deleted"}


# ------------------------- App Settings (public read) --------------------
@router.get("/app")
async def list_app_settings(database: AsyncIOMotorDatabase = Depends(db)):
    """Public read of app settings — no auth required so mobile PWAs can bootstrap."""
    cursor = database.app_settings.find({"deleted_at": None})
    out = {}
    async for d in cursor:
        out[d["key"]] = d.get("value")
    return out


@router.get("/app/{key}")
async def get_app_setting(key: str, database: AsyncIOMotorDatabase = Depends(db)):
    doc = await database.app_settings.find_one({"key": key, "deleted_at": None})
    if not doc:
        raise HTTPException(404, "Setting not found")
    return _clean(doc)


@router.put("/app/admin")
async def admin_upsert_app_setting(
    body: AppSettingUpsert,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    now = datetime.now(timezone.utc).isoformat()
    doc = await database.app_settings.find_one_and_update(
        {"key": body.key, "deleted_at": None},
        {
            "$set": {
                "value": body.value,
                "description": body.description,
                "updated_at": now,
                "updated_by": admin["mobile"],
            },
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "key": body.key,
                "created_at": now,
                "created_by": admin["mobile"],
                "deleted_at": None,
            },
        },
        upsert=True,
        return_document=True,
    )
    return _clean(doc)


@router.delete("/app/admin/{key}")
async def admin_delete_app_setting(
    key: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    result = await database.app_settings.update_one(
        {"key": key, "deleted_at": None},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat(), "updated_by": admin["mobile"]}},
    )
    if result.modified_count == 0:
        raise HTTPException(404, "Setting not found")
    return {"message": "Setting deleted"}


# ------------------------- System Configuration (admin only) -------------
@router.get("/system", response_model=PaginatedResponse)
async def admin_list_system_config(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    query: dict = {"deleted_at": None}
    if search:
        query["$or"] = [
            {"key": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]
    total = await database.system_configuration.count_documents(query)
    cursor = (
        database.system_configuration.find(query)
        .sort("key", 1)
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


@router.put("/system")
async def admin_upsert_system_config(
    body: SystemConfigurationUpsert,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    now = datetime.now(timezone.utc).isoformat()
    doc = await database.system_configuration.find_one_and_update(
        {"key": body.key, "deleted_at": None},
        {
            "$set": {
                "value": body.value,
                "description": body.description,
                "updated_at": now,
                "updated_by": admin["mobile"],
            },
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "key": body.key,
                "created_at": now,
                "created_by": admin["mobile"],
                "deleted_at": None,
            },
        },
        upsert=True,
        return_document=True,
    )
    return _clean(doc)


@router.delete("/system/{key}")
async def admin_delete_system_config(
    key: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    result = await database.system_configuration.update_one(
        {"key": key, "deleted_at": None},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat(), "updated_by": admin["mobile"]}},
    )
    if result.modified_count == 0:
        raise HTTPException(404, "System configuration not found")
    return {"message": "System configuration deleted"}
