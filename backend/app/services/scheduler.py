"""Background scheduler — runs periodic tasks on the FastAPI event loop.

Currently only fires the expiring-validity scan once per day at 03:00 IST.
Adding more tasks: just append entries to `SCHEDULE`.

The scheduler is started from `server.py`'s startup event and cancelled on
shutdown. Each iteration is wrapped in a try/except so a single failed job
never kills the loop.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("scheduler")

# IST is UTC+5:30. We store the target in IST but compute the next
# fire moment in UTC to avoid DST surprises (India doesn't observe DST,
# so this is truly stable).
IST_OFFSET = timedelta(hours=5, minutes=30)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _next_ist_time(hh: int, mm: int) -> datetime:
    """Return the next UTC moment corresponding to `hh:mm` IST.
    If today's slot has passed, returns tomorrow's."""
    now = _now_utc()
    ist_now = now + IST_OFFSET
    target_ist = ist_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target_ist <= ist_now:
        target_ist = target_ist + timedelta(days=1)
    return target_ist - IST_OFFSET


async def _scan_expiring_job(db: AsyncIOMotorDatabase) -> int:
    """Idempotently fire validity-expiring notifications for anyone in the
    last 7 days of validity."""
    from app.services.notify import validity_expiring as _notify_exp

    now = _now_utc()
    created = 0
    async for p in db.program_purchases.find(
        {"status": "active", "deleted_at": None}
    ):
        try:
            exp = datetime.fromisoformat(p["expiry_date"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        days_left = (exp - now).days
        if days_left > 7 or days_left < 0:
            continue
        prog = await db.programs.find_one(
            {"id": p["program_id"]}, {"name": 1}
        ) or {}
        res = await _notify_exp(
            db,
            membership_id=p["user_membership_id"],
            program_name=prog.get("name", "your program"),
            program_id=p["program_id"],
            days_left=days_left,
            expiry_date=p["expiry_date"],
        )
        if res:
            created += 1
    return created


async def _run_daily(hh: int, mm: int, name: str, job, db):
    """Sleep until the next hh:mm IST tick, run the job, log, repeat."""
    while True:
        target = _next_ist_time(hh, mm)
        delay = (target - _now_utc()).total_seconds()
        logger.info("scheduler '%s' sleeping %.0fs until %s UTC", name, delay, target.isoformat())
        try:
            await asyncio.sleep(max(1, delay))
        except asyncio.CancelledError:
            logger.info("scheduler '%s' cancelled", name)
            return
        try:
            n = await job(db)
            logger.info("scheduler '%s' fired — %s notifications sent", name, n)
        except Exception as exc:  # noqa: BLE001
            logger.exception("scheduler '%s' failed: %s", name, exc)


_tasks: list[asyncio.Task] = []


def start(db: AsyncIOMotorDatabase) -> None:
    """Kick off all daily background jobs. Idempotent — repeated calls are
    silently ignored (used to survive uvicorn hot-reload)."""
    if _tasks:
        return
    loop = asyncio.get_event_loop()
    _tasks.append(
        loop.create_task(_run_daily(3, 0, "scan_expiring", _scan_expiring_job, db))
    )
    logger.info("scheduler started: %d job(s)", len(_tasks))


def stop() -> None:
    for t in _tasks:
        t.cancel()
    _tasks.clear()
