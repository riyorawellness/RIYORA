"""Bank Details — user get/upsert, admin read/delete.

Account number is stored obfuscated (last 4 shown) in list responses. Full
number is only returned to the owning user and admin on explicit detail fetch.
Encryption at rest is a future infrastructure task; the schema is ready.
"""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import BankDetailsUpsert, PaginatedResponse

router = APIRouter(prefix="/bank-details", tags=["Bank Details"])


def _masked(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    acc = doc.get("account_number", "")
    doc["account_number_masked"] = f"****{acc[-4:]}" if len(acc) >= 4 else "****"
    return doc


@router.get("/me")
async def get_my_bank(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    doc = await database.bank_details.find_one(
        {"user_membership_id": current["membership_id"], "deleted_at": None}
    )
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


@router.put("/me")
async def upsert_my_bank(
    body: BankDetailsUpsert,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc).isoformat()
    doc = await database.bank_details.find_one_and_update(
        {"user_membership_id": current["membership_id"], "deleted_at": None},
        {
            "$set": {
                **body.model_dump(),
                "updated_at": now,
                "updated_by": current["membership_id"],
                "verification_status": "pending",  # reset on any change
            },
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "user_membership_id": current["membership_id"],
                "created_at": now,
                "created_by": current["membership_id"],
                "deleted_at": None,
            },
        },
        upsert=True,
        return_document=True,
    )
    doc.pop("_id", None)
    return doc


@router.delete("/me")
async def delete_my_bank(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    result = await database.bank_details.update_one(
        {"user_membership_id": current["membership_id"], "deleted_at": None},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.modified_count == 0:
        raise HTTPException(404, "No bank details on file")
    return {"message": "Bank details removed"}


# ------------------------- Admin ------------------------------------------
@router.get("/admin", response_model=PaginatedResponse)
async def admin_list_bank(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    verification_status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    query: dict = {"deleted_at": None}
    if verification_status:
        query["verification_status"] = verification_status
    if search:
        rx = {"$regex": search, "$options": "i"}
        query["$or"] = [{"account_holder": rx}, {"bank_name": rx}, {"user_membership_id": rx}]
    total = await database.bank_details.count_documents(query)
    cursor = (
        database.bank_details.find(query)
        .sort("updated_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    async for d in cursor:
        items.append(_masked(d))
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/admin/{user_membership_id}")
async def admin_get_bank(
    user_membership_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    doc = await database.bank_details.find_one(
        {"user_membership_id": user_membership_id, "deleted_at": None}
    )
    if not doc:
        raise HTTPException(404, "Bank details not found")
    doc.pop("_id", None)
    return doc


@router.post("/admin/{user_membership_id}/verify")
async def admin_verify_bank(
    user_membership_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    result = await database.bank_details.find_one_and_update(
        {"user_membership_id": user_membership_id, "deleted_at": None},
        {
            "$set": {
                "verification_status": "verified",
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": admin["mobile"],
            }
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(404, "Bank details not found")
    result.pop("_id", None)
    return result
