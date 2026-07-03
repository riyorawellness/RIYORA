"""Membership ID generation: format RW + 6 numeric digits, unique."""
import secrets

from motor.motor_asyncio import AsyncIOMotorDatabase


async def generate_membership_id(db: AsyncIOMotorDatabase) -> str:
    """Generate a unique RW###### id. Uses secrets for unpredictability.

    Collision-resistant: 1M keyspace, retries up to 20 times before raising.
    """
    for _ in range(20):
        digits = f"{secrets.randbelow(1_000_000):06d}"
        if digits == "000000":
            continue  # reserved for company
        candidate = f"RW{digits}"
        exists = await db.memberships.find_one({"membership_id": candidate})
        if not exists:
            return candidate
    raise RuntimeError("Unable to generate a unique Membership ID after 20 attempts")
