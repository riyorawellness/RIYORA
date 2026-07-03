"""Program Purchases — metadata storage only. Payment gateway is later phase.

- User: list my purchases, get one.
- Admin: create/update/delete/list any purchase (manual grant supported).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import (
    PaginatedResponse,
    ProgramPurchaseCreate,
    ProgramPurchaseUpdate,
)
from app.repositories.base import BaseRepository

router = APIRouter(prefix="/purchases", tags=["Program Purchases"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(database, "program_purchases", ["invoice_number"], "-purchase_date,-created_at")


@router.get("/me", response_model=PaginatedResponse)
async def list_my_purchases(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    program_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str = Query(default="-purchase_date"),
):
    filters = {"user_membership_id": current["membership_id"]}
    if program_id:
        filters["program_id"] = program_id
    if status:
        filters["status"] = status
    return await _repo(database).list_paginated(filters, None, sort, page, page_size)


@router.get("/me/{purchase_id}")
async def get_my_purchase(
    purchase_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    doc = await _repo(database).get_by({"id": purchase_id, "user_membership_id": current["membership_id"]})
    if not doc:
        raise HTTPException(404, "Purchase not found")
    return doc


# ------------------------- Admin ------------------------------------------
@router.get("/admin", response_model=PaginatedResponse)
async def admin_list_purchases(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    user_membership_id: str | None = Query(default=None),
    program_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str = Query(default="-purchase_date"),
):
    filters = {}
    if user_membership_id:
        filters["user_membership_id"] = user_membership_id
    if program_id:
        filters["program_id"] = program_id
    if status:
        filters["status"] = status
    return await _repo(database).list_paginated(filters, search, sort, page, page_size)


@router.post("/admin", status_code=201)
async def admin_create_purchase(
    body: ProgramPurchaseCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    user = await database.users.find_one({"membership_id": body.user_membership_id, "deleted_at": None})
    if not user:
        raise HTTPException(400, "user_membership_id does not exist")
    program = await database.programs.find_one({"id": body.program_id, "deleted_at": None})
    if not program:
        raise HTTPException(400, "program_id does not exist")
    if await database.program_purchases.find_one({"invoice_number": body.invoice_number, "deleted_at": None}):
        raise HTTPException(409, "invoice_number already exists")
    return await _repo(database).create(body.model_dump(), actor=admin["mobile"])


@router.put("/admin/{purchase_id}")
async def admin_update_purchase(
    purchase_id: str,
    body: ProgramPurchaseUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updated = await _repo(database).update(purchase_id, body.model_dump(exclude_none=True), actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Purchase not found")
    return updated


@router.delete("/admin/{purchase_id}")
async def admin_delete_purchase(
    purchase_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    ok = await _repo(database).soft_delete(purchase_id, actor=admin["mobile"])
    if not ok:
        raise HTTPException(404, "Purchase not found")
    return {"message": "Purchase deleted"}
