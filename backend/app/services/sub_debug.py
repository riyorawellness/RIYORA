"""Subscription-flow diagnostic logger.

Every server-side Razorpay call related to subscriptions and every
frontend state transition in the subscription-checkout modal is appended
here so the admin can trace an entire mandate attempt end-to-end from
the /admin/qa/sub-debug page.

This is *diagnostic-only* — no business logic reads from it. Rows are
capped at 5000 total via a simple `_gc()` call at insert time.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

MAX_ROWS = 5000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(obj: Any, seen_secrets: tuple[str, ...] = ("secret", "signature", "password")) -> Any:
    """Best-effort redaction of secret-looking values before persisting."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(s in str(k).lower() for s in seen_secrets):
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v, seen_secrets)
        return out
    if isinstance(obj, list):
        return [_redact(v, seen_secrets) for v in obj]
    return obj


async def log_event(
    db: AsyncIOMotorDatabase,
    *,
    source: str,               # "backend" | "frontend" | "webhook"
    stage: str,                # "init.start" | "init.plan_created" | "checkout.opened" | ...
    subscription_id: str | None = None,
    program_id: str | None = None,
    membership_id: str | None = None,
    ok: bool = True,
    message: str = "",
    payload: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    """Insert one diagnostic row. Never raises — logging failure must NOT
    break the caller's business flow."""
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "source": source,
            "stage": stage,
            "subscription_id": subscription_id,
            "program_id": program_id,
            "membership_id": membership_id,
            "ok": bool(ok),
            "message": (message or "")[:1000],
            "payload": _redact(payload or {}),
            "error": _redact(error or {}) if error else None,
            "created_at": _now(),
        }
        await db.sub_debug_events.insert_one(doc)
        # opportunistic ring-buffer trim
        cnt = await db.sub_debug_events.estimated_document_count()
        if cnt > MAX_ROWS:
            oldest = (
                await db.sub_debug_events
                .find({}, {"_id": 1})
                .sort("created_at", 1)
                .to_list(length=cnt - MAX_ROWS)
            )
            if oldest:
                await db.sub_debug_events.delete_many(
                    {"_id": {"$in": [o["_id"] for o in oldest]}}
                )
    except Exception:  # noqa: BLE001
        logger.exception("sub_debug.log_event failed (non-fatal)")
