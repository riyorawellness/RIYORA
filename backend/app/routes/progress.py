"""Program Progress — user get + update (auto-upsert), admin read + update."""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import PaginatedResponse, ProgramProgressUpdate
from app.repositories.base import BaseRepository

router = APIRouter(prefix="/progress", tags=["Program Progress"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(database, "program_progress", [], "-updated_at")


async def _upsert_progress(
    database: AsyncIOMotorDatabase,
    user_id: str,
    program_id: str,
    updates: dict,
    actor: str,
) -> dict:
    updates = {k: v for k, v in updates.items() if v is not None}
    now = datetime.now(timezone.utc).isoformat()
    # Defaults applied only on insert (do NOT overlap with $set fields).
    set_on_insert = {
        "id": uuid.uuid4().hex,
        "user_membership_id": user_id,
        "program_id": program_id,
        "created_at": now,
        "created_by": actor,
        "deleted_at": None,
    }
    if "completed_modules" not in updates:
        set_on_insert["completed_modules"] = []
    if "percentage" not in updates:
        set_on_insert["percentage"] = 0
    if "certificate_eligible" not in updates:
        set_on_insert["certificate_eligible"] = False

    result = await database.program_progress.find_one_and_update(
        {"user_membership_id": user_id, "program_id": program_id, "deleted_at": None},
        {
            "$set": {**updates, "updated_at": now, "updated_by": actor},
            "$setOnInsert": set_on_insert,
        },
        upsert=True,
        return_document=True,
    )
    if result is not None:
        result.pop("_id", None)
    return result or {}


@router.get("/me/{program_id}")
async def get_my_progress(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    doc = await database.program_progress.find_one(
        {"user_membership_id": current["membership_id"], "program_id": program_id, "deleted_at": None}
    )
    if not doc:
        # Return a virtual empty record so clients can rely on shape.
        return {
            "user_membership_id": current["membership_id"],
            "program_id": program_id,
            "completed_modules": [],
            "current_module_id": None,
            "percentage": 0,
            "completion_date": None,
            "certificate_eligible": False,
        }
    doc.pop("_id", None)
    return doc


@router.put("/me/{program_id}")
async def update_my_progress(
    program_id: str,
    body: ProgramProgressUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    if not await database.programs.find_one({"id": program_id, "deleted_at": None}):
        raise HTTPException(400, "program_id does not exist")
    return await _upsert_progress(
        database, current["membership_id"], program_id, body.model_dump(exclude_none=True), current["membership_id"]
    )


# ------------------------- Admin ------------------------------------------
@router.get("/admin", response_model=PaginatedResponse)
async def admin_list_progress(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    user_membership_id: str | None = Query(default=None),
    program_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="-updated_at"),
):
    filters = {}
    if user_membership_id:
        filters["user_membership_id"] = user_membership_id
    if program_id:
        filters["program_id"] = program_id
    return await _repo(database).list_paginated(filters, None, sort, page, page_size)


@router.put("/admin/{user_membership_id}/{program_id}")
async def admin_update_progress(
    user_membership_id: str,
    program_id: str,
    body: ProgramProgressUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    return await _upsert_progress(
        database, user_membership_id, program_id, body.model_dump(exclude_none=True), admin["mobile"]
    )
