"""Deep health checks — DB ping, collection counts, uptime, error rate."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin

router = APIRouter(prefix="/health", tags=["Health"])

_START = time.time()


@router.get("/live")
async def live():
    return {"status": "alive"}


@router.get("/ready")
async def ready(database: AsyncIOMotorDatabase = Depends(db)):
    try:
        await database.command("ping")
        return {"status": "ready", "mongo": "ok"}
    except Exception as e:
        return {"status": "degraded", "mongo": str(e)}


@router.get("/deep")
async def deep(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Admin-only in-depth health snapshot."""
    started = time.perf_counter()
    mongo_ok = True
    err = None
    try:
        await database.command("ping")
    except Exception as e:  # noqa: BLE001
        mongo_ok = False
        err = str(e)
    ping_ms = int((time.perf_counter() - started) * 1000)

    counts = {}
    for c in [
        "users", "admins", "memberships", "programs", "program_purchases",
        "commissions", "payouts", "notifications", "activity_log",
        "activity_sessions", "cms_pages", "banners",
    ]:
        counts[c] = await database[c].count_documents({})

    # Errors last 24h (admin logs with 'error' or 5xx audit rows if any)
    yesterday_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    errors_24h = await database.activity_log.count_documents(
        {"created_at": {"$gte": yesterday_iso}, "action": {"$regex": "error|fail", "$options": "i"}}
    )
    uptime_s = int(time.time() - _START)
    return {
        "status": "ok" if mongo_ok else "degraded",
        "mongo_ping_ms": ping_ms,
        "mongo_ok": mongo_ok,
        "mongo_error": err,
        "uptime_seconds": uptime_s,
        "counts": counts,
        "errors_24h": errors_24h,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
