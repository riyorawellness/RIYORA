"""Enrolment + subscription endpoints (2026-07 rewrite).

DESIGN — Post the AutoPay/UPI-mandate rewrite:
- **Free programs** → POST /api/programs/{id}/enrol-free (unchanged) creates
  a row in `program_enrolments`.

- **Subscription programs** → **no more Razorpay Subscriptions / Plans /
  Mandates**. A subscription is now just a normal one-time Razorpay order
  for one cycle's amount. When paid, the resulting `program_purchases`
  row carries `expiry_date = now + cycle_days` (30 / 180 / 365). When the
  purchase expires, the user hits "Renew" and pays for the next cycle
  through the exact same checkout flow. This eliminates every mandate-
  race bug we hit with the AutoPay implementation.
  → No new endpoints. Frontend uses the existing /api/payments/order
    endpoint for both first purchase and renewals.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_user
from app.utils.audit import log_action

router = APIRouter(tags=["Payments · Enrolment"])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
#  FREE PROGRAM ENROLMENT
# ============================================================================

@router.post("/programs/{program_id}/enrol-free", status_code=201)
async def enrol_free(
    program_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    program = await database.programs.find_one({"id": program_id, "deleted_at": None, "is_active": True})
    if not program:
        raise HTTPException(404, "Program not found or inactive.")
    if program.get("payment_type") != "free":
        raise HTTPException(400, "This program is not free.")

    membership_id = current["membership_id"]
    existing = await database.program_enrolments.find_one(
        {"user_membership_id": membership_id, "program_id": program_id, "deleted_at": None}
    )
    if existing:
        raise HTTPException(409, "You are already enrolled in this program.")

    doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": membership_id,
        "program_id": program_id,
        "program_name": program.get("name"),
        "source": "free",
        "status": "active",
        "created_at": _iso(),
        "updated_at": _iso(),
        "deleted_at": None,
    }
    await database.program_enrolments.insert_one(doc)
    await log_action(
        database,
        actor_id=membership_id,
        action="enrol.free",
        entity="program",
        entity_id=program_id,
    )
    doc.pop("_id", None)
    return doc


@router.get("/programs/me/enrolments")
async def my_enrolments(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    out = []
    async for r in database.program_enrolments.find(
        {"user_membership_id": current["membership_id"], "deleted_at": None}
    ).sort("created_at", -1):
        r.pop("_id", None)
        out.append(r)
    return {"items": out, "total": len(out)}
