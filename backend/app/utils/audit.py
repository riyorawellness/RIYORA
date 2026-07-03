"""Simple audit log writer."""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase


async def log_action(
    db: AsyncIOMotorDatabase,
    actor_id: str | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    await db.audit_logs.insert_one(
        {
            "actor_id": actor_id,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
