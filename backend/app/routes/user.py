"""User profile routes."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_user
from app.models.schemas import UpdateProfileRequest, UserPublic
from app.utils.serializers import user_to_public

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/profile", response_model=UserPublic)
async def get_profile(current: dict = Depends(get_current_user)):
    return user_to_public(current)


@router.put("/profile", response_model=UserPublic)
async def update_profile(
    body: UpdateProfileRequest,
    current: dict = Depends(get_current_user),
    database: AsyncIOMotorDatabase = Depends(db),
):
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await database.users.update_one({"_id": current["_id"]}, {"$set": updates})
        current.update(updates)
        # Reflect name change in memberships tree.
        if "full_name" in updates:
            await database.memberships.update_one(
                {"membership_id": current["membership_id"]},
                {"$set": {"owner_name": updates["full_name"], "updated_at": updates["updated_at"]}},
            )
    return user_to_public(current)
