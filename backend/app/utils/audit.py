"""Simple audit log writer.

Writes to the shared `activity_log` collection so that the Phase 7 audit-log
viewer (`GET /api/admin/audit-log`) surfaces admin actions alongside user
activity emitted by other modules (payments, referrals, etc.).
"""
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase


async def log_action(
    db: AsyncIOMotorDatabase,
    actor_id: str | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    meta: dict | None = None,
    metadata: dict | None = None,
) -> None:
    payload_meta = meta if meta is not None else (metadata or {})
    await db.activity_log.insert_one(
        {
            "id": str(uuid.uuid4()),
            "actor_membership_id": actor_id,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "meta": payload_meta,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
