"""Program Modules — user list/get, admin CRUD.

Note: sequential unlock enforcement is NOT implemented in this phase (business
logic phase later). Modules simply store an `order_index`, `module_number` and
`sequential_unlock` flag for future enforcement.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import (
    PaginatedResponse,
    ProgramModuleCreate,
    ProgramModuleUpdate,
)
from app.repositories.base import BaseRepository

router = APIRouter(prefix="/modules", tags=["Program Modules"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(database, "program_modules", ["name", "description"], "order_index,module_number")


@router.get("", response_model=PaginatedResponse)
async def list_modules(
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user),
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
    return await _repo(database).list_paginated(filters, search, sort, page, page_size)


@router.get("/{module_id}")
async def get_module(
    module_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user),
):
    doc = await _repo(database).get(module_id)
    if not doc:
        raise HTTPException(404, "Module not found")
    return doc


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
