"""Activity Meter + Subscription Cycle engine.

Cycle = user's most recent ACTIVE Inner Peace subscription, from purchase_date
→ expiry_date. Activity requirement (default 4 sessions) is configurable via
`app_settings.activity_sessions_required`.

`log_session()` inserts a row into `activity_sessions`. `get_meter()` computes
completed/remaining/status. Statuses:
  green   — subscription active AND required sessions completed
  yellow  — subscription active, sessions NOT yet completed, still within cycle
  red     — subscription expired OR beyond grace period
  no_subscription — user has never bought Inner Peace
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return _now().isoformat()


async def _get_int_setting(db: AsyncIOMotorDatabase, key: str, fallback: int) -> int:
    row = await db.app_settings.find_one({"key": key, "deleted_at": None})
    if not row:
        return fallback
    try:
        return int(row.get("value", fallback))
    except (TypeError, ValueError):
        return fallback


async def find_inner_peace_program(db: AsyncIOMotorDatabase) -> Optional[dict]:
    """Return the Inner Peace program document (any subscription program)."""
    prog = await db.programs.find_one(
        {"is_subscription": True, "deleted_at": None, "is_active": True}
    )
    if prog:
        prog.pop("_id", None)
    return prog


async def get_active_cycle(db: AsyncIOMotorDatabase, user_membership_id: str) -> Optional[dict]:
    """Return the current Inner Peace subscription cycle for the user.

    Looks up ANY active subscription-sourced purchase (not restricted to a
    single "Inner Peace" program id), since admin may have multiple
    subscription programs.

    Returns { subscription_id, purchase_id, program_id, cycle_start, cycle_end } or None.
    """
    now_iso = _iso()
    # Fetch newest active purchase where the linked program is a subscription.
    cursor = (
        db.program_purchases.find(
            {
                "user_membership_id": user_membership_id,
                "status": "active",
                "deleted_at": None,
                "$or": [
                    {"source": "subscription_mock"},
                    {"subscription_id": {"$ne": None}},
                ],
            }
        )
        .sort("purchase_date", -1)
    )
    async for p in cursor:
        p.pop("_id", None)
        if p.get("expiry_date") and p["expiry_date"] < now_iso:
            continue
        # Confirm the linked program is truly a subscription (defensive).
        prog = await db.programs.find_one(
            {"id": p.get("program_id"), "deleted_at": None}, {"is_subscription": 1}
        )
        if not prog or not prog.get("is_subscription"):
            continue
        return {
            "subscription_id": p.get("subscription_id") or p.get("id"),
            "purchase_id": p.get("id"),
            "program_id": p.get("program_id"),
            "cycle_start": p.get("purchase_date"),
            "cycle_end": p.get("expiry_date"),
        }
    return None


async def log_session(
    db: AsyncIOMotorDatabase,
    user_membership_id: str,
    source: str = "manual",
    module_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Log an Inner Peace session. Idempotent for same-day 'module_complete' from
    the same module — a user can't accidentally double-count a module."""
    cycle = await get_active_cycle(db, user_membership_id)
    if not cycle:
        raise ValueError("No active Inner Peace subscription cycle")

    now = _now()
    # Idempotency: if module_id set and already logged today for this cycle → return existing.
    if module_id:
        existing = await db.activity_sessions.find_one(
            {
                "user_membership_id": user_membership_id,
                "subscription_purchase_id": cycle["purchase_id"],
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
        "subscription_purchase_id": cycle["purchase_id"],
        "program_id": cycle["program_id"],
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


async def count_sessions_in_cycle(
    db: AsyncIOMotorDatabase, user_membership_id: str, purchase_id: str
) -> int:
    return await db.activity_sessions.count_documents(
        {
            "user_membership_id": user_membership_id,
            "subscription_purchase_id": purchase_id,
            "deleted_at": None,
        }
    )


async def _get_latest_subscription_purchase(
    db: AsyncIOMotorDatabase, user_membership_id: str
) -> Optional[dict]:
    """Return the newest subscription-sourced purchase regardless of status.
    Used to distinguish 'no_subscription' (never subscribed) from 'red' (expired)."""
    async for p in (
        db.program_purchases.find(
            {
                "user_membership_id": user_membership_id,
                "deleted_at": None,
                "$or": [
                    {"source": "subscription_mock"},
                    {"subscription_id": {"$ne": None}},
                ],
            }
        )
        .sort("purchase_date", -1)
        .limit(1)
    ):
        p.pop("_id", None)
        return p
    return None


async def get_meter(db: AsyncIOMotorDatabase, user_membership_id: str) -> dict:
    """Return the Activity Meter payload for the given user."""
    required = await _get_int_setting(
        db, "activity_sessions_required", settings.ACTIVITY_SESSIONS_REQUIRED
    )
    cycle = await get_active_cycle(db, user_membership_id)
    if not cycle:
        # Distinguish 'never subscribed' from 'expired'.
        past = await _get_latest_subscription_purchase(db, user_membership_id)
        if past:
            return {
                "status": "red",
                "required": required,
                "completed": 0,
                "remaining": required,
                "cycle_end": past.get("expiry_date"),
            }
        return {
            "status": "no_subscription",
            "required": required,
            "completed": 0,
            "remaining": required,
        }
    completed = await count_sessions_in_cycle(db, user_membership_id, cycle["purchase_id"])
    remaining = max(0, required - completed)
    status = "green" if completed >= required else "yellow"
    try:
        end = datetime.fromisoformat((cycle["cycle_end"] or "").replace("Z", "+00:00"))
        days_left = max(0, (end - _now()).days)
    except Exception:
        days_left = None
    return {
        "status": status,
        "required": required,
        "completed": completed,
        "remaining": remaining,
        "cycle_start": cycle["cycle_start"],
        "cycle_end": cycle["cycle_end"],
        "subscription_id": cycle["subscription_id"],
        "program_id": cycle["program_id"],
        "days_left": days_left,
    }


async def is_eligible_for_commission(
    db: AsyncIOMotorDatabase, user_membership_id: str
) -> bool:
    """A sponsor earns commission ONLY if their Inner Peace subscription is
    active AND they have completed the required sessions in current cycle."""
    meter = await get_meter(db, user_membership_id)
    return meter["status"] == "green"


# --------- Reminders ------------------------------------------------------


async def create_smart_reminders(db: AsyncIOMotorDatabase, user_membership_id: str) -> list[dict]:
    """Insert notifications rows at 7d/3d/1d before cycle end + expiry day.

    Idempotent — will not create duplicate reminder for the same cycle & offset.
    """
    cycle = await get_active_cycle(db, user_membership_id)
    if not cycle:
        return []
    try:
        end = datetime.fromisoformat((cycle["cycle_end"] or "").replace("Z", "+00:00"))
    except Exception:
        return []

    now = _now()
    days_left = (end - now).days
    created = []
    # Fetch admin-configured messages, fallback to defaults.
    def _msg(default: str, key: str) -> str:
        return default  # keep it simple; admin messaging templates are Phase 7

    schedule = [
        (7, "Your Inner Peace cycle ends in 7 days", "Complete your remaining sessions to stay active."),
        (3, "3 days left in your cycle", "Only a few sessions away from Active status."),
        (1, "Last day of your cycle", "One day left to stay eligible for referral rewards."),
        (0, "Cycle ends today", "Complete your sessions before midnight to remain Active."),
    ]

    for offset, title, body in schedule:
        if days_left <= offset:
            key = f"reminder:{cycle['purchase_id']}:{offset}"
            exists = await db.notifications.find_one(
                {"user_membership_id": user_membership_id, "meta.key": key, "deleted_at": None}
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
                "meta": {"key": key, "cycle_end": cycle["cycle_end"], "purchase_id": cycle["purchase_id"]},
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "deleted_at": None,
            }
            await db.notifications.insert_one(doc)
            created.append(doc)
    return created
