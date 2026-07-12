"""Admin Preview Mode — impersonation + test-mode purchase.

Endpoints (all require an admin token):
  POST /api/admin/preview/impersonate/{membership_id}
      Returns a short-lived user-role access token for the target user,
      carrying an `impersonated_by=<admin_mobile>` JWT claim so downstream
      routes can detect the preview session and audit it.

  POST /api/admin/preview/mark-paid
      Body: {program_id, plan?: "monthly"|"yearly"}
      Called with the impersonation user token (NOT the admin token). Creates
      a `program_purchases` row with source='admin_preview' to grant access
      without commissions or invoice. Idempotent per (user, program).

Security:
  - Impersonation TTL: 30 minutes (shorter than the normal 60-min access).
  - JWT `impersonated_by` claim is required to call `mark-paid`.
  - Every impersonation and mark-paid is written to `activity_log`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.core.security import _encode
from app.services.validity import compute_expiry, get_active_purchase
from app.utils.audit import log_action

router = APIRouter(prefix="/admin/preview", tags=["Admin Preview"])

PREVIEW_TTL_MIN = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_preview_access_token(user_membership_id: str, admin_mobile: str) -> str:
    now = _now()
    payload = {
        "sub": user_membership_id,
        "role": "user",
        "type": "access",
        "impersonated_by": admin_mobile,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=PREVIEW_TTL_MIN)).timestamp()),
    }
    return _encode(payload)


@router.post("/impersonate/{membership_id}")
async def start_preview(
    membership_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    # Block impersonation of the company root, defence in depth (checked
    # before the users lookup because RW000000 lives in `memberships`, not
    # `users`).
    if membership_id == "RW000000":
        raise HTTPException(403, "Cannot impersonate the company account")

    user = await database.users.find_one(
        {"membership_id": membership_id, "deleted_at": None}
    )
    if not user:
        raise HTTPException(404, "User not found")

    token = _create_preview_access_token(membership_id, admin["mobile"])

    await log_action(
        database,
        actor_id=admin["mobile"],
        action="preview.impersonate",
        entity="user",
        entity_id=membership_id,
        meta={"admin": admin["mobile"], "target": membership_id},
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": PREVIEW_TTL_MIN,
        "user": {
            "membership_id": user["membership_id"],
            "full_name": user.get("full_name"),
            "mobile": user.get("mobile"),
            "state": user.get("state"),
            "city": user.get("city"),
            "referral_id": user.get("referral_id"),
            "sponsor_membership_id": user.get("sponsor_membership_id"),
            "role": "user",
        },
        "preview": True,
        "impersonated_by": admin["mobile"],
    }


@router.post("/mark-paid")
async def mark_program_paid(
    body: dict = Body(...),
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Grant access to a program without payment. Requires an active
    impersonation token — regular user tokens are rejected."""
    if not current.get("_impersonated_by"):
        raise HTTPException(
            403,
            "This endpoint is only usable during an admin preview session.",
        )
    program_id = (body or {}).get("program_id")
    if not program_id:
        raise HTTPException(400, "program_id is required")

    program = await database.programs.find_one(
        {"id": program_id, "deleted_at": None}
    )
    if not program:
        raise HTTPException(404, "Program not found")

    if await get_active_purchase(database, current["membership_id"], program_id):
        return {"success": True, "message": "Already has active access", "created": False}

    now_dt = _now()
    validity = int(program.get("validity_days") or 365)
    purchase_doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": current["membership_id"],
        "program_id": program_id,
        "payment_request_id": None,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "utr": None,
        "price_paid": 0.0,
        "discount": 0.0,
        "taxable_amount": 0.0,
        "gst_percent": 0.0,
        "gst_amount": 0.0,
        "total": 0.0,
        "invoice_number": f"INV-PREVIEW-{uuid.uuid4().hex[:10].upper()}",
        "purchase_date": now_dt.isoformat(),
        "expiry_date": compute_expiry(now_dt, validity).isoformat(),
        "renewal_date": None,
        "status": "active",
        "payment_status": "preview",
        "source": "admin_preview",
        "is_mock": True,
        "created_at": now_dt.isoformat(),
        "updated_at": now_dt.isoformat(),
        "deleted_at": None,
    }
    await database.program_purchases.insert_one(purchase_doc)
    purchase_doc.pop("_id", None)

    await log_action(
        database,
        actor_id=current["_impersonated_by"],
        action="preview.mark_paid",
        entity="program_purchase",
        entity_id=purchase_doc["id"],
        meta={
            "admin": current["_impersonated_by"],
            "target": current["membership_id"],
            "program_id": program_id,
            "program_name": program.get("name"),
        },
    )

    return {
        "success": True,
        "created": True,
        "purchase": purchase_doc,
        "message": f"'{program.get('name')}' unlocked in preview mode",
    }
