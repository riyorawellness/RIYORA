"""Activity Meter — rolling 30-day cycle from user registration.

New rules (2026-02):
- User must complete N sessions (default 4) in every rolling 30-day cycle to
  stay "active". Cycle #0 starts at registration; each subsequent cycle rolls
  30 days later.
- A session = completing ANY module of ANY program the user has purchased
  (subscription OR one-time) that's still within validity. Auto-logged from
  `mark_module_completed()` in program_engine.
- Statuses:
    green   — required sessions met in current cycle
    yellow  — grace period (first-ever cycle, not yet met)
    red     — cycle not first AND requirement not met -> account inactive
    no_plan — user has no active purchase at all
- Commission eligibility (sponsor payouts) fires only on `green`.
- Home page shows a reactivation banner on `red` / `no_plan`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings

settings = get_settings()

CYCLE_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).isoformat()


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


async def _get_int_setting(db: AsyncIOMotorDatabase, key: str, fallback: int) -> int:
    row = await db.app_settings.find_one({"key": key, "deleted_at": None})
    if not row:
        return fallback
    try:
        return int(row.get("value", fallback))
    except (TypeError, ValueError):
        return fallback


async def _get_user_registered_at(
    db: AsyncIOMotorDatabase, user_membership_id: str
) -> Optional[datetime]:
    user = await db.users.find_one(
        {"membership_id": user_membership_id, "deleted_at": None},
        {"created_at": 1},
    )
    return _parse_iso((user or {}).get("created_at"))


async def has_any_active_purchase(
    db: AsyncIOMotorDatabase, user_membership_id: str
) -> bool:
    """True if the user owns ANY program (subscription or one-time) still
    within its validity window."""
    now_iso = _iso()
    cursor = db.program_purchases.find(
        {
            "user_membership_id": user_membership_id,
            "status": "active",
            "deleted_at": None,
        }
    ).limit(50)
    async for p in cursor:
        exp = p.get("expiry_date")
        if not exp or exp > now_iso:
            return True
    return False


def compute_cycle(registered_at: datetime, at: Optional[datetime] = None) -> dict:
    """Given a registration timestamp, compute the rolling 30-day cycle window
    that contains `at` (defaults to now)."""
    at = at or _now()
    if at < registered_at:
        at = registered_at
    delta_days = (at - registered_at).days
    cycle_number = delta_days // CYCLE_DAYS
    cycle_start = registered_at + timedelta(days=cycle_number * CYCLE_DAYS)
    cycle_end = cycle_start + timedelta(days=CYCLE_DAYS)
    return {
        "cycle_number": cycle_number,
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
    }


async def count_sessions_in_cycle(
    db: AsyncIOMotorDatabase,
    user_membership_id: str,
    cycle_start: datetime,
    cycle_end: datetime,
) -> int:
    return await db.activity_sessions.count_documents(
        {
            "user_membership_id": user_membership_id,
            "completed_at": {
                "$gte": cycle_start.isoformat(),
                "$lt": cycle_end.isoformat(),
            },
            "deleted_at": None,
        }
    )


async def log_session(
    db: AsyncIOMotorDatabase,
    user_membership_id: str,
    source: str = "manual",
    program_id: Optional[str] = None,
    module_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Log a module-completion session. The user must own ANY active
    purchase; the specific program doesn't matter for the counter.

    Idempotent for `module_complete` events on the same module — a completed
    module contributes exactly ONE session towards the meter, regardless of
    how many times the user re-visits it.
    """
    if not await has_any_active_purchase(db, user_membership_id):
        raise ValueError("No active plan or subscription")

    now = _now()
    if module_id:
        existing = await db.activity_sessions.find_one(
            {
                "user_membership_id": user_membership_id,
                "module_id": module_id,
                "deleted_at": None,
            }
        )
        if existing:
            existing.pop("_id", None)
            return existing

    doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": user_membership_id,
        "program_id": program_id,
        "module_id": module_id,
        "source": source,
        "notes": notes,
        "completed_at": now.isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "deleted_at": None,
    }
    await db.activity_sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def get_meter(db: AsyncIOMotorDatabase, user_membership_id: str) -> dict:
    """Return the activity meter payload for the user."""
    required = await _get_int_setting(
        db, "activity_sessions_required", settings.ACTIVITY_SESSIONS_REQUIRED
    )
    registered_at = await _get_user_registered_at(db, user_membership_id)
    if not registered_at:
        return {
            "status": "no_plan",
            "required": required,
            "completed": 0,
            "remaining": required,
        }

    has_plan = await has_any_active_purchase(db, user_membership_id)
    cycle = compute_cycle(registered_at)
    completed = await count_sessions_in_cycle(
        db, user_membership_id, cycle["cycle_start"], cycle["cycle_end"]
    )
    remaining = max(0, required - completed)
    now = _now()
    days_left = max(0, (cycle["cycle_end"] - now).days)

    if not has_plan:
        status = "no_plan"
    elif completed >= required:
        status = "green"
    elif cycle["cycle_number"] == 0:
        status = "yellow"  # first cycle grace: user is active by default
    else:
        status = "red"

    return {
        "status": status,
        "required": required,
        "completed": completed,
        "remaining": remaining,
        "cycle_number": cycle["cycle_number"],
        "cycle_start": cycle["cycle_start"].isoformat(),
        "cycle_end": cycle["cycle_end"].isoformat(),
        "days_left": days_left,
        "has_active_plan": has_plan,
    }


async def is_eligible_for_commission(
    db: AsyncIOMotorDatabase, user_membership_id: str
) -> bool:
    """A sponsor earns commission ONLY if their meter is green (i.e. active
    plan AND required sessions completed in current cycle)."""
    meter = await get_meter(db, user_membership_id)
    return meter["status"] == "green"


# --------- Reminders ------------------------------------------------------


async def create_smart_reminders(
    db: AsyncIOMotorDatabase, user_membership_id: str
) -> list[dict]:
    """Insert notification rows at 7d/3d/1d before cycle end + expiry day.

    Idempotent — will not create duplicate reminder for the same cycle & offset.
    """
    registered_at = await _get_user_registered_at(db, user_membership_id)
    if not registered_at:
        return []
    cycle = compute_cycle(registered_at)
    now = _now()
    days_left = (cycle["cycle_end"] - now).days
    cycle_key = f"cycle:{cycle['cycle_number']}"

    schedule = [
        (7, "Your activity cycle ends in 7 days",
         "Complete your remaining sessions to stay active."),
        (3, "3 days left in your cycle",
         "Only a few sessions away from staying Active."),
        (1, "Last day of your cycle",
         "One day left to stay eligible for referral rewards."),
        (0, "Cycle ends today",
         "Complete your sessions before midnight to remain Active."),
    ]

    created = []
    for offset, title, body in schedule:
        if days_left <= offset:
            key = f"reminder:{cycle_key}:{offset}"
            exists = await db.notifications.find_one(
                {
                    "user_membership_id": user_membership_id,
                    "meta.key": key,
                    "deleted_at": None,
                }
            )
            if exists:
                continue
            doc = {
                "id": str(uuid.uuid4()),
                "user_membership_id": user_membership_id,
                "title": title,
                "body": body,
                "category": "activity",
                "is_broadcast": False,
                "is_read": False,
                "meta": {
                    "key": key,
                    "cycle_end": cycle["cycle_end"].isoformat(),
                    "cycle_number": cycle["cycle_number"],
                },
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "deleted_at": None,
            }
            await db.notifications.insert_one(doc)
            created.append(doc)
    return created
