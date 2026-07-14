"""Admin User Management — search, edit, suspend, reset password, profile, export."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin
from app.core.security import hash_password
from app.models.phase7 import (
    AdminResetUserPassword,
    AdminUserStatusUpdate,
    AdminUserUpdate,
)
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from app.services.activity_meter import get_meter
from app.services.commission_engine import summarise_user
from app.utils.audit import log_action
from app.utils.membership import generate_membership_id

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("")
async def list_users(
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
    q: str | None = Query(default=None),
    state: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    login_method: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    filters: dict = {"deleted_at": None}
    if state:
        filters["state"] = state
    if is_active is not None:
        filters["is_active"] = is_active
    if login_method:
        if login_method == "legacy":
            filters["firebase_uid"] = {"$in": [None, ""]}
        else:
            filters["login_method"] = login_method
    if q:
        filters["$or"] = [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"mobile": {"$regex": q}},
            {"membership_id": {"$regex": q, "$options": "i"}},
            {"sponsor_membership_id": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"firebase_uid": {"$regex": q, "$options": "i"}},
        ]
    total = await database.users.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for u in (
        database.users.find(filters).sort("created_at", -1).skip(skip).limit(page_size)
    ):
        items.append(
            {
                "membership_id": u["membership_id"],
                "full_name": u["full_name"],
                "mobile": u["mobile"],
                "state": u.get("state"),
                "city": u.get("city"),
                "sponsor_membership_id": u.get("sponsor_membership_id"),
                "sponsor_name": u.get("sponsor_name"),
                "is_active": u.get("is_active", True),
                "is_dummy": bool(u.get("is_dummy", False)),
                "status": u.get("status", "active" if u.get("is_active", True) else "deactivated"),
                "firebase_uid": u.get("firebase_uid"),
                "email": u.get("email"),
                "email_verified": bool(u.get("email_verified", False)),
                "login_method": u.get("login_method") or ("legacy" if not u.get("firebase_uid") else None),
                "photo_url": u.get("photo_url"),
                "last_login_at": u.get("last_login_at"),
                "created_at": u["created_at"],
            }
        )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


@router.get("/export")
async def export_users(
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "membership_id", "full_name", "mobile", "state", "city",
            "sponsor_membership_id", "sponsor_name", "status",
            "is_active", "created_at",
        ]
    )
    async for u in database.users.find({"deleted_at": None}).sort("created_at", -1):
        writer.writerow(
            [
                u.get("membership_id"),
                u.get("full_name"),
                u.get("mobile"),
                u.get("state"),
                u.get("city"),
                u.get("sponsor_membership_id"),
                u.get("sponsor_name"),
                u.get("status", "active" if u.get("is_active", True) else "deactivated"),
                u.get("is_active", True),
                u.get("created_at"),
            ]
        )
    await log_action(database, actor_id=admin["mobile"], action="users.export", entity="users")
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="users.csv"'},
    )


@router.get("/{membership_id}")
async def user_detail(
    membership_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    u = await database.users.find_one({"membership_id": membership_id, "deleted_at": None})
    if not u:
        raise HTTPException(404, "User not found")
    u.pop("_id", None)
    u.pop("password_hash", None)

    # Purchases
    purchases = []
    async for p in database.program_purchases.find(
        {"user_membership_id": membership_id, "deleted_at": None}
    ).sort("purchase_date", -1):
        p.pop("_id", None)
        prog = await database.programs.find_one({"id": p["program_id"], "deleted_at": None}, {"name": 1})
        p["program_name"] = (prog or {}).get("name")
        purchases.append(p)

    # Subscriptions
    subs = []
    async for s in database.subscriptions.find(
        {"user_membership_id": membership_id, "deleted_at": None}
    ).sort("created_at", -1):
        s.pop("_id", None)
        subs.append(s)

    # Bank details
    bank = await database.bank_details.find_one(
        {"user_membership_id": membership_id, "deleted_at": None}
    )
    if bank:
        bank.pop("_id", None)

    # Downline counts
    downline: dict = {"L1": 0, "L2": 0, "L3": 0}
    ids = [membership_id]
    for lvl in (1, 2, 3):
        next_ids = []
        async for d in database.referral_tree.find(
            {"sponsor_membership_id": {"$in": ids}, "deleted_at": None},
            {"user_membership_id": 1},
        ):
            downline[f"L{lvl}"] += 1
            next_ids.append(d["user_membership_id"])
        ids = next_ids

    # Earnings + activity
    earnings = await summarise_user(database, membership_id)
    activity = await get_meter(database, membership_id)

    return {
        "user": u,
        "purchases": purchases,
        "subscriptions": subs,
        "bank_details": bank,
        "downline": downline,
        "earnings": earnings,
        "activity": activity,
    }


@router.patch("/{membership_id}")
async def update_user(
    membership_id: str,
    body: AdminUserUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_at"] = _iso()
    res = await database.users.update_one(
        {"membership_id": membership_id, "deleted_at": None}, {"$set": updates}
    )
    if not res.matched_count:
        raise HTTPException(404, "User not found")
    await log_action(
        database,
        actor_id=admin["mobile"],
        action="users.update",
        entity="user",
        entity_id=membership_id,
        meta=updates,
    )
    return {"success": True, "updated": list(updates.keys())}


@router.patch("/{membership_id}/status")
async def update_user_status(
    membership_id: str,
    body: AdminUserStatusUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    is_active = body.status == "active"
    res = await database.users.update_one(
        {"membership_id": membership_id, "deleted_at": None},
        {
            "$set": {
                "status": body.status,
                "is_active": is_active,
                "status_reason": body.reason,
                "updated_at": _iso(),
            }
        },
    )
    if not res.matched_count:
        raise HTTPException(404, "User not found")
    # Revoke sessions when suspending or deactivating.
    if not is_active:
        await database.refresh_tokens.update_many(
            {"user_id": membership_id, "role": "user"},
            {"$set": {"revoked": True}},
        )
    await log_action(
        database,
        actor_id=admin["mobile"],
        action=f"users.status.{body.status}",
        entity="user",
        entity_id=membership_id,
        meta={"reason": body.reason},
    )
    return {"success": True, "status": body.status}


@router.post("/{membership_id}/reset-password")
async def reset_user_password(
    membership_id: str,
    body: AdminResetUserPassword,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    res = await database.users.update_one(
        {"membership_id": membership_id, "deleted_at": None},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": _iso()}},
    )
    if not res.matched_count:
        raise HTTPException(404, "User not found")
    # Revoke sessions.
    await database.refresh_tokens.update_many(
        {"user_id": membership_id, "role": "user"}, {"$set": {"revoked": True}}
    )
    await log_action(
        database,
        actor_id=admin["mobile"],
        action="users.password.reset",
        entity="user",
        entity_id=membership_id,
    )
    return {"success": True}



# =============================================================================
# DUMMY (TESTER) USERS
# =============================================================================
# A dummy user is a normal user account marked with `is_dummy=True`. They log
# in via the standard /auth/login flow, see the entire app like a real user,
# but on the checkout screen they can hit "Mark as Paid" instead of paying —
# their purchases carry `source='dummy'` and are filtered out of revenue
# reports / analytics. No commissions are triggered.


class CreateDummyUserRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr = Field(..., description="Primary login identifier for the tester.")
    password: str = Field(min_length=6, max_length=64)
    mobile: Optional[str] = Field(default=None, min_length=10, max_length=15, description="Optional; auto-generated placeholder if omitted (users.mobile is uniquely indexed).")
    state: str = Field(default="TEST", max_length=60)
    city: str = Field(default="TEST", max_length=60)
    sponsor_membership_id: str = Field(default="RW000000", max_length=20)


@router.post("/dummy", status_code=201)
async def create_dummy_user(
    body: CreateDummyUserRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    """Create a tester (dummy) user without OTP / Firebase verification.

    Admin-only. Since the app now authenticates with email+password (Firebase
    for real users; legacy /auth/login for testers who don't have Firebase
    accounts), the tester's PRIMARY identifier is now `email`. A synthetic
    unique placeholder mobile is generated so the users.mobile unique
    index is satisfied without asking the admin for one.
    """
    email = body.email.strip().lower()

    # Email uniqueness — dummy users must not collide with real accounts.
    if await database.users.find_one({"email": email, "deleted_at": None}):
        raise HTTPException(status_code=409, detail="Email already registered")

    # Mobile: use whatever admin provided, else auto-generate a unique 10-digit
    # starting with 9 (satisfies the Indian mobile regex used elsewhere).
    mobile = (body.mobile or "").strip()
    if mobile:
        if await database.users.find_one({"mobile": mobile, "deleted_at": None}):
            raise HTTPException(status_code=409, detail="Mobile already registered")
    else:
        # ms-since-epoch modulo 1e9 → 9-digit tail → prefix with '9' to keep
        # a valid pattern. Loop the tiny chance of a collision.
        import time
        for _ in range(5):
            mobile = "9" + f"{int(time.time()*1000) % 10**9:09d}"
            if not await database.users.find_one({"mobile": mobile, "deleted_at": None}):
                break
        else:
            raise HTTPException(500, "Could not generate a unique placeholder mobile — please retry.")

    # Sponsor must exist
    sponsor = await database.memberships.find_one(
        {"membership_id": body.sponsor_membership_id, "deleted_at": None}
    )
    if not sponsor:
        raise HTTPException(status_code=400, detail="Invalid Sponsor / Referral ID")

    membership_id = await generate_membership_id(database)
    now = _iso()

    user_doc = {
        "full_name": body.full_name,
        "mobile": mobile,
        "email": email,
        "email_verified": True,  # admin-vouched — no verification email flow for testers
        "login_method": "email",
        "state": body.state,
        "city": body.city,
        "password_hash": hash_password(body.password),
        "role": "user",
        "membership_id": membership_id,
        "sponsor_membership_id": sponsor["membership_id"],
        "sponsor_name": sponsor.get("owner_name"),
        "is_active": True,
        "is_dummy": True,
        "created_at": now,
        "updated_at": now,
        "joining_date": now,
        "deleted_at": None,
    }
    result = await database.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    await database.memberships.insert_one(
        {
            "membership_id": membership_id,
            "owner_name": body.full_name,
            "user_id": str(result.inserted_id),
            "sponsor_membership_id": sponsor["membership_id"],
            "is_company": False,
            "is_active": True,
            "is_dummy": True,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )
    sponsor_tree = await database.referral_tree.find_one(
        {"user_membership_id": sponsor["membership_id"]}
    )
    depth = (sponsor_tree.get("level", 0) if sponsor_tree else 0) + 1
    await database.referral_tree.insert_one(
        {
            "user_membership_id": membership_id,
            "sponsor_membership_id": sponsor["membership_id"],
            "level": depth,
            "joining_date": now,
            "status": "active",
            "is_dummy": True,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )
    await database.profiles.insert_one(
        {
            "user_membership_id": membership_id,
            "email": email,
            "dob": None,
            "gender": None,
            "address": None,
            "profile_photo_url": None,
            "occupation": None,
            "alt_contact": None,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )

    await log_action(
        database,
        actor_id=admin["mobile"],
        action="users.dummy.create",
        entity="user",
        entity_id=membership_id,
        meta={"email": email, "mobile": mobile, "full_name": body.full_name},
    )

    return {
        "success": True,
        "membership_id": membership_id,
        "email": email,
        "mobile": mobile,
        "full_name": body.full_name,
        "is_dummy": True,
    }
