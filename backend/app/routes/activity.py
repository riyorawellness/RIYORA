"""Activity Meter routes — meter + manual session logging + smart reminders."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_user
from app.models.phase6 import SessionLogCreate
from app.services.activity_meter import (
    create_smart_reminders,
    get_meter,
    log_session,
)

router = APIRouter(prefix="/activity", tags=["Activity Meter"])


@router.get("/meter")
async def my_meter(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    return await get_meter(database, current["membership_id"])


@router.post("/session", status_code=201)
async def log_activity_session(
    body: SessionLogCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    try:
        doc = await log_session(
            database,
            current["membership_id"],
            source=body.source,
            module_id=body.module_id,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    meter = await get_meter(database, current["membership_id"])
    return {"session": doc, "meter": meter}


@router.get("/sessions/me")
async def my_sessions(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    limit: int = 50,
):
    items = []
    async for s in database.activity_sessions.find(
        {"user_membership_id": current["membership_id"], "deleted_at": None}
    ).sort("completed_at", -1).limit(limit):
        s.pop("_id", None)
        items.append(s)
    return {"items": items}


@router.post("/reminders/generate", status_code=201)
async def generate_my_reminders(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    created = await create_smart_reminders(database, current["membership_id"])
    return {"created": len(created), "items": created}
