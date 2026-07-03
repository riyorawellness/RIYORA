"""Program Validity Engine.

Computes expiry dates on purchase and provides fast validity checks.
Programs are considered active if:
  * At least one purchase row exists for (user, program_id) with status='active'
  * And now < expiry_date

If the program is a subscription (is_subscription=True), the same rules apply
based on the current subscription cycle's expiry_date.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


def _now() -> datetime:
    return datetime.now(timezone.utc)


def compute_expiry(purchase_date: datetime, validity_days: int) -> datetime:
    return purchase_date + timedelta(days=int(validity_days))


async def get_active_purchase(
    db: AsyncIOMotorDatabase, user_membership_id: str, program_id: str
) -> Optional[dict]:
    """Return the newest ACTIVE (not expired) purchase for the user+program, else None."""
    now_iso = _now().isoformat()
    cursor = (
        db.program_purchases.find(
            {
                "user_membership_id": user_membership_id,
                "program_id": program_id,
                "status": "active",
                "deleted_at": None,
            }
        )
        .sort("purchase_date", -1)
        .limit(1)
    )
    async for p in cursor:
        p.pop("_id", None)
        exp = p.get("expiry_date")
        if not exp or exp > now_iso:
            return p
    return None


async def mark_expired_purchases(
    db: AsyncIOMotorDatabase, user_membership_id: str
) -> int:
    """Set status='expired' on all rows whose expiry_date is past.

    Called opportunistically on user-facing reads so the dashboard is accurate.
    """
    now_iso = _now().isoformat()
    result = await db.program_purchases.update_many(
        {
            "user_membership_id": user_membership_id,
            "status": "active",
            "expiry_date": {"$lt": now_iso},
            "deleted_at": None,
        },
        {"$set": {"status": "expired", "updated_at": now_iso}},
    )
    return result.modified_count
