"""Enrolment endpoints — free-program enrolment only.

Note: Razorpay Subscriptions / AutoPay / UPI-mandate flows have been REMOVED
(2026-07-19). The Razorpay live account does not have Subscriptions activated,
so all recurring plans are now sold as regular one-time purchases via the
`/api/payments/order` + `/api/payments/verify` flow. When a purchase expires
the user simply repurchases through the same one-time checkout.
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
