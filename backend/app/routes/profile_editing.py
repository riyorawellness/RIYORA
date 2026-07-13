"""User self-service profile editing + email/mobile change-request workflow.

Design:
- Users can DIRECTLY edit "soft" fields (dob, gender, address, photo,
  profession, blood group, emergency contact, about-me, name pronunciation,
  state/district/city/pincode) via PATCH /api/users/me. Every change
  is diff-logged to activity_log.

- Users CANNOT directly change their email or mobile — those are the
  primary account identifiers. They must submit a change request via
  POST /api/users/me/change-request. An admin must approve it via
  POST /api/admin/change-requests/{id}/approve while re-entering their
  own admin password (defense-in-depth against stolen admin cookies).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.core.security import verify_password
from app.models.phase2 import AdminApprovalBody, ChangeRequestCreate, ProfileUpdate
from app.utils.audit import log_action
from app.utils.serializers import user_to_public

router = APIRouter(tags=["User · Self-service"])
admin_router = APIRouter(prefix="/admin/change-requests", tags=["Admin · Change requests"])

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ============================================================================
#  USER
# ============================================================================

@router.patch("/users/me")
async def edit_my_profile(
    body: ProfileUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Update the signed-in user's own editable profile fields. Any field
    absent from the request body is left untouched. `email` and `mobile`
    are refused — those require the change-request workflow below."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields provided.")

    # Diff for audit log — record only fields that actually changed.
    diff = {}
    for k, v in updates.items():
        if current.get(k) != v:
            diff[k] = {"from": current.get(k), "to": v}
    if not diff:
        return user_to_public(current)

    now = datetime.now(timezone.utc).isoformat()
    updates["updated_at"] = now
    await database.users.update_one({"_id": current["_id"]}, {"$set": updates})

    # Keep the legacy /profiles doc in sync for any field that has an
    # analogous column there.
    mirror_keys = {"dob", "gender", "address", "profile_photo_url", "occupation", "alt_contact"}
    profile_updates = {k: v for k, v in updates.items() if k in mirror_keys}
    if profile_updates:
        profile_updates["updated_at"] = now
        await database.profiles.update_one(
            {"user_membership_id": current["membership_id"], "deleted_at": None},
            {
                "$set": profile_updates,
                "$setOnInsert": {
                    "user_membership_id": current["membership_id"],
                    "created_at": now,
                    "deleted_at": None,
                },
            },
            upsert=True,
        )

    await log_action(
        database,
        actor_id=current["membership_id"],
        action="profile.edit",
        entity="user",
        entity_id=current["membership_id"],
        meta={"diff": diff},
    )
    fresh = await database.users.find_one({"_id": current["_id"]})
    return user_to_public(fresh)


@router.post("/users/me/change-request")
async def submit_change_request(
    body: ChangeRequestCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Ask an admin to change your email or mobile number."""
    new_val = body.new_value.strip()
    if body.field == "email":
        if not EMAIL_RE.match(new_val):
            raise HTTPException(400, "Enter a valid email address.")
    elif body.field == "mobile":
        if not MOBILE_RE.match(new_val):
            raise HTTPException(400, "Enter a valid 10-digit Indian mobile.")

    # Duplicate protection — reject requests whose new value already
    # belongs to a different membership.
    dup_query = {body.field: new_val, "deleted_at": None, "_id": {"$ne": current["_id"]}}
    if await database.users.find_one(dup_query):
        raise HTTPException(409, f"This {body.field} is already in use by another RIYORA member.")

    # One pending request per (user, field) — the user should cancel /
    # wait rather than pile up parallel asks.
    existing = await database.change_requests.find_one(
        {"user_membership_id": current["membership_id"], "field": body.field, "status": "pending"}
    )
    if existing:
        raise HTTPException(409, f"You already have a pending {body.field} change request.")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": current["membership_id"],
        "user_full_name": current.get("full_name"),
        "field": body.field,
        "current_value": current.get(body.field),
        "new_value": new_val,
        "reason": (body.reason or "").strip() or None,
        "status": "pending",
        "requested_at": now,
        "reviewed_at": None,
        "reviewer_id": None,
        "reviewer_note": None,
    }
    await database.change_requests.insert_one(doc)
    await log_action(
        database,
        actor_id=current["membership_id"],
        action="change_request.submit",
        entity="change_request",
        entity_id=doc["id"],
        meta={"field": body.field, "new_value": new_val},
    )
    # Notify admins via the shared notifications collection so the CRM
    # dashboard surfaces the request.
    await database.notifications.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_membership_id": None,  # broadcast to admins
            "audience": "admin",
            "title": f"Profile change request ({body.field})",
            "body": f"{current.get('full_name')} ({current['membership_id']}) requested a {body.field} change.",
            "category": "change_request",
            "meta": {"change_request_id": doc["id"], "field": body.field},
            "read_at": None,
            "created_at": now,
        }
    )
    doc.pop("_id", None)
    return doc


@router.get("/users/me/change-requests")
async def list_my_change_requests(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    cursor = database.change_requests.find(
        {"user_membership_id": current["membership_id"]}
    ).sort("requested_at", -1)
    out = []
    async for d in cursor:
        d.pop("_id", None)
        out.append(d)
    return {"items": out, "total": len(out)}


# ============================================================================
#  ADMIN
# ============================================================================

async def _reverify_admin(database: AsyncIOMotorDatabase, admin: dict, password: str) -> None:
    """Re-authenticate the admin against their stored password hash. This is
    critical for destructive actions — a bearer token alone is not enough."""
    if not password:
        raise HTTPException(400, "Admin password is required to approve/reject this request.")
    fresh = await database.admins.find_one({"_id": admin["_id"], "deleted_at": None})
    if not fresh or not verify_password(password, fresh["password_hash"]):
        raise HTTPException(401, "Incorrect admin password.")


@admin_router.get("")
async def admin_list_change_requests(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    status: str | None = None,
):
    query: dict = {}
    if status in {"pending", "approved", "rejected"}:
        query["status"] = status
    cursor = database.change_requests.find(query).sort("requested_at", -1).limit(500)
    items = []
    async for d in cursor:
        d.pop("_id", None)
        items.append(d)
    pending = await database.change_requests.count_documents({"status": "pending"})
    return {"items": items, "total": len(items), "pending": pending}


@admin_router.post("/{request_id}/approve")
async def admin_approve_change_request(
    request_id: str,
    body: AdminApprovalBody,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    await _reverify_admin(database, admin, body.admin_password)

    req = await database.change_requests.find_one({"id": request_id})
    if not req:
        raise HTTPException(404, "Change request not found.")
    if req["status"] != "pending":
        raise HTTPException(409, f"Request is already {req['status']}.")

    user = await database.users.find_one(
        {"membership_id": req["user_membership_id"], "deleted_at": None}
    )
    if not user:
        raise HTTPException(404, "Requesting user no longer exists.")

    # Re-check duplicate at approval time (someone else could have grabbed
    # the value between request and approval).
    dup = await database.users.find_one(
        {req["field"]: req["new_value"], "deleted_at": None, "_id": {"$ne": user["_id"]}}
    )
    if dup:
        raise HTTPException(409, f"This {req['field']} is now in use by another member — cannot approve.")

    now = datetime.now(timezone.utc).isoformat()
    updates = {req["field"]: req["new_value"], "updated_at": now}
    # Approved email change forces the verified flag to false so the user
    # must re-verify their new address via Firebase.
    if req["field"] == "email":
        updates["email_verified"] = False
    await database.users.update_one({"_id": user["_id"]}, {"$set": updates})
    await database.change_requests.update_one(
        {"id": request_id},
        {
            "$set": {
                "status": "approved",
                "reviewed_at": now,
                "reviewer_id": admin["mobile"],
                "reviewer_note": (body.note or "").strip() or None,
            }
        },
    )
    await log_action(
        database,
        actor_id=admin["mobile"],
        action="change_request.approve",
        entity="change_request",
        entity_id=request_id,
        meta={
            "field": req["field"],
            "from": req["current_value"],
            "to": req["new_value"],
            "user": req["user_membership_id"],
        },
    )
    # In-app notification for the requesting user.
    await database.notifications.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_membership_id": user["membership_id"],
            "title": f"Your {req['field']} change was approved",
            "body": f"Your {req['field']} has been updated to {req['new_value']}.",
            "category": "change_request",
            "meta": {"change_request_id": request_id, "field": req["field"]},
            "read_at": None,
            "created_at": now,
        }
    )
    return {"status": "approved", "request_id": request_id}


@admin_router.post("/{request_id}/reject")
async def admin_reject_change_request(
    request_id: str,
    body: AdminApprovalBody,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    await _reverify_admin(database, admin, body.admin_password)

    req = await database.change_requests.find_one({"id": request_id})
    if not req:
        raise HTTPException(404, "Change request not found.")
    if req["status"] != "pending":
        raise HTTPException(409, f"Request is already {req['status']}.")

    now = datetime.now(timezone.utc).isoformat()
    await database.change_requests.update_one(
        {"id": request_id},
        {
            "$set": {
                "status": "rejected",
                "reviewed_at": now,
                "reviewer_id": admin["mobile"],
                "reviewer_note": (body.note or "").strip() or None,
            }
        },
    )
    await log_action(
        database,
        actor_id=admin["mobile"],
        action="change_request.reject",
        entity="change_request",
        entity_id=request_id,
        meta={"field": req["field"], "user": req["user_membership_id"], "reason": body.note},
    )
    await database.notifications.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_membership_id": req["user_membership_id"],
            "title": f"Your {req['field']} change was rejected",
            "body": (body.note or "Please contact support if you need help."),
            "category": "change_request",
            "meta": {"change_request_id": request_id, "field": req["field"]},
            "read_at": None,
            "created_at": now,
        }
    )
    return {"status": "rejected", "request_id": request_id}
