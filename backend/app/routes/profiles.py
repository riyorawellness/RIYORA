"""Extended user profile — email, dob, gender, address, photo, occupation, alt_contact."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import PaginatedResponse, ProfileUpdate

router = APIRouter(prefix="/profiles", tags=["Profiles"])


def _clean(d: dict | None) -> dict | None:
    if d is None:
        return None
    d.pop("_id", None)
    return d


@router.get("/me")
async def get_my_profile(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    doc = await database.profiles.find_one(
        {"user_membership_id": current["membership_id"], "deleted_at": None}
    )
    if not doc:
        return {
            "user_membership_id": current["membership_id"],
            "email": None,
            "dob": None,
            "gender": None,
            "address": None,
            "profile_photo_url": None,
            "occupation": None,
            "alt_contact": None,
        }
    return _clean(doc)


@router.put("/me")
async def update_my_profile(
    body: ProfileUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    updates = body.model_dump(exclude_none=True)
    now = datetime.now(timezone.utc).isoformat()
    doc = await database.profiles.find_one_and_update(
        {"user_membership_id": current["membership_id"], "deleted_at": None},
        {
            "$set": {**updates, "updated_at": now},
            "$setOnInsert": {
                "user_membership_id": current["membership_id"],
                "created_at": now,
                "deleted_at": None,
            },
        },
        upsert=True,
        return_document=True,
    )
    return _clean(doc)


# ------------------------- Admin ------------------------------------------
@router.get("/admin", response_model=PaginatedResponse)
async def admin_list_profiles(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    query: dict = {"deleted_at": None}
    if search:
        rx = {"$regex": search, "$options": "i"}
        query["$or"] = [{"email": rx}, {"user_membership_id": rx}, {"occupation": rx}]
    total = await database.profiles.count_documents(query)
    cursor = (
        database.profiles.find(query).sort("updated_at", -1).skip((page - 1) * page_size).limit(page_size)
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


@router.get("/admin/{user_membership_id}")
async def admin_get_profile(
    user_membership_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    doc = await database.profiles.find_one(
        {"user_membership_id": user_membership_id, "deleted_at": None}
    )
    if not doc:
        raise HTTPException(404, "Profile not found")
    return _clean(doc)
