"""Program Modules — user list/get, admin CRUD.

Phase 4: User endpoint enforces access + module unlock status.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user, get_current_user_or_admin
from app.models.phase2 import (
    PaginatedResponse,
    ProgramModuleCreate,
    ProgramModuleUpdate,
)
from app.repositories.base import BaseRepository
from app.services.program_engine import is_module_unlocked
from app.services.validity import get_active_purchase

router = APIRouter(prefix="/modules", tags=["Program Modules"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(database, "program_modules", ["name", "description"], "order_index,module_number")


@router.get("", response_model=PaginatedResponse)
async def list_modules(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user_or_admin),
    program_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="module_number"),
):
    filters = {}
    if program_id:
        filters["program_id"] = program_id
    if is_active is not None:
        filters["is_active"] = is_active
    elif not current.get("is_admin"):
        filters["is_active"] = True
    return await _repo(database).list_paginated(filters, search, sort, page, page_size)


@router.get("/{module_id}")
async def get_module(
    module_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user_or_admin),
):
    doc = await _repo(database).get(module_id)
    if not doc:
        raise HTTPException(404, "Module not found")
    return doc


# ---------------------- Phase 4: user-facing enriched list ----------------


@router.get("/me/by-program/{program_id}")
async def my_program_modules(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Return modules for a program with unlock + completed flags.

    Requires an active purchase; strips raw video/audio/pdf URLs so users can
    only stream via /content/token (Phase 4 security).
    """
    if not await database.programs.find_one({"id": program_id, "deleted_at": None}):
        raise HTTPException(404, "Program not found")

    active = await get_active_purchase(database, current["membership_id"], program_id)
    has_access = bool(active)

    modules = []
    async for m in database.program_modules.find(
        {"program_id": program_id, "deleted_at": None, "is_active": True}
    ).sort("module_number", 1):
        m.pop("_id", None)
        modules.append(m)

    prog = await database.program_progress.find_one(
        {"user_membership_id": current["membership_id"], "program_id": program_id, "deleted_at": None}
    )
    completed = set((prog or {}).get("completed_modules") or [])

    out = []
    for m in modules:
        unlocked = has_access and await is_module_unlocked(
            database, current["membership_id"], program_id, m
        )
        entry = {
            "id": m["id"],
            "module_number": m.get("module_number"),
            "name": m.get("name"),
            "description": m.get("description"),
            "quiz_id": m.get("quiz_id"),
            "assignment": m.get("assignment"),
            "order_index": m.get("order_index"),
            "sequential_unlock": m.get("sequential_unlock", True),
            "has_video": bool(m.get("video_url")),
            "has_audio": bool(m.get("audio_url")),
            "has_pdf": bool(m.get("pdf_url")),
            "is_unlocked": unlocked,
            "is_completed": m["id"] in completed,
        }
        out.append(entry)

    return {"has_access": has_access, "active_purchase": active, "modules": out}


# ------------------------- Admin ------------------------------------------
@router.post("/admin", status_code=201)
async def admin_create_module(
    body: ProgramModuleCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    if not await database.programs.find_one({"id": body.program_id, "deleted_at": None}):
        raise HTTPException(400, "program_id does not exist")
    exists = await database.program_modules.find_one(
        {"program_id": body.program_id, "module_number": body.module_number, "deleted_at": None}
    )
    if exists:
        raise HTTPException(409, "module_number already exists for this program")
    return await _repo(database).create(body.model_dump(), actor=admin["mobile"])


@router.put("/admin/{module_id}")
async def admin_update_module(
    module_id: str,
    body: ProgramModuleUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updated = await _repo(database).update(module_id, body.model_dump(exclude_none=True), actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Module not found")
    return updated


@router.delete("/admin/{module_id}")
async def admin_delete_module(
    module_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    ok = await _repo(database).soft_delete(module_id, actor=admin["mobile"])
    if not ok:
        raise HTTPException(404, "Module not found")
    return {"message": "Module deleted"}
