"""Program Categories — user list, admin CRUD."""
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user_or_admin
from app.models.phase2 import (
    PaginatedResponse,
    ProgramCategoryCreate,
    ProgramCategoryUpdate,
)
from app.repositories.base import BaseRepository

router = APIRouter(prefix="/categories", tags=["Program Categories"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(database, "program_categories", ["name", "slug", "description"], "order_index")


@router.get("", response_model=PaginatedResponse)
async def list_categories(
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user_or_admin),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="order_index"),
    is_active: bool | None = Query(default=None),
):
    filters = {}
    if is_active is not None:
        filters["is_active"] = is_active
    return await _repo(database).list_paginated(filters, search, sort, page, page_size)


@router.get("/{category_id}")
async def get_category(
    category_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user_or_admin),
):
    doc = await _repo(database).get(category_id)
    if not doc:
        raise HTTPException(404, "Category not found")
    return doc


# ------------------------- Admin ------------------------------------------
@router.post("/admin", status_code=201)
async def admin_create_category(
    body: ProgramCategoryCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    exists = await database.program_categories.find_one({"slug": body.slug, "deleted_at": None})
    if exists:
        raise HTTPException(409, "Category slug already exists")
    return await _repo(database).create(body.model_dump(), actor=admin["mobile"])


@router.put("/admin/{category_id}")
async def admin_update_category(
    category_id: str,
    body: ProgramCategoryUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updated = await _repo(database).update(category_id, body.model_dump(exclude_none=True), actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Category not found")
    return updated


@router.delete("/admin/{category_id}")
async def admin_delete_category(
    category_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    ok = await _repo(database).soft_delete(category_id, actor=admin["mobile"])
    if not ok:
        raise HTTPException(404, "Category not found")
    return {"message": "Category deleted"}
