"""Programs — user list/get (active only), admin full CRUD + activate/deactivate."""
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import PaginatedResponse, ProgramCreate, ProgramUpdate
from app.repositories.base import BaseRepository

router = APIRouter(prefix="/programs", tags=["Programs"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(
        database,
        "programs",
        ["name", "slug", "short_description", "description"],
        "order_index",
    )


@router.get("", response_model=PaginatedResponse)
async def list_programs(
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user),
    search: str | None = Query(default=None),
    category_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=True),
    is_subscription: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str = Query(default="order_index,-created_at"),
):
    filters = {}
    if category_id:
        filters["category_id"] = category_id
    if is_active is not None:
        filters["is_active"] = is_active
    if is_subscription is not None:
        filters["is_subscription"] = is_subscription
    return await _repo(database).list_paginated(filters, search, sort, page, page_size)


@router.get("/{program_id}")
async def get_program(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user),
):
    doc = await _repo(database).get(program_id)
    if not doc:
        raise HTTPException(404, "Program not found")
    return doc


# ------------------------- Admin ------------------------------------------
@router.post("/admin", status_code=201)
async def admin_create_program(
    body: ProgramCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    if body.category_id:
        cat = await database.program_categories.find_one({"id": body.category_id, "deleted_at": None})
        if not cat:
            raise HTTPException(400, "category_id does not exist")
    if await database.programs.find_one({"slug": body.slug, "deleted_at": None}):
        raise HTTPException(409, "Program slug already exists")
    return await _repo(database).create(body.model_dump(), actor=admin["mobile"])


@router.put("/admin/{program_id}")
async def admin_update_program(
    program_id: str,
    body: ProgramUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updates = body.model_dump(exclude_none=True)
    if "category_id" in updates:
        cat = await database.program_categories.find_one({"id": updates["category_id"], "deleted_at": None})
        if not cat:
            raise HTTPException(400, "category_id does not exist")
    updated = await _repo(database).update(program_id, updates, actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Program not found")
    return updated


@router.post("/admin/{program_id}/activate")
async def admin_activate(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updated = await _repo(database).update(program_id, {"is_active": True}, actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Program not found")
    return updated


@router.post("/admin/{program_id}/deactivate")
async def admin_deactivate(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updated = await _repo(database).update(program_id, {"is_active": False}, actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Program not found")
    return updated


@router.delete("/admin/{program_id}")
async def admin_delete(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    ok = await _repo(database).soft_delete(program_id, actor=admin["mobile"])
    if not ok:
        raise HTTPException(404, "Program not found")
    return {"message": "Program deleted"}
