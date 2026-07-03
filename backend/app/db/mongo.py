"""MongoDB client singleton, index setup and seed logic.

Using MongoDB as PostgreSQL fallback per spec. Collections mirror the tables
listed in the requirements: users, admins, profiles, memberships,
otp_verifications, refresh_tokens, settings, notifications, audit_logs.
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.security import hash_password

settings = get_settings()

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URL)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.DB_NAME]


async def create_indexes() -> None:
    db = get_db()
    # users
    await db.users.create_index("mobile", unique=True)
    await db.users.create_index("membership_id", unique=True)
    await db.users.create_index("referral_id")
    await db.users.create_index("sponsor_membership_id")
    # admins
    await db.admins.create_index("mobile", unique=True)
    # memberships (mirror of tree)
    await db.memberships.create_index("membership_id", unique=True)
    await db.memberships.create_index("sponsor_membership_id")
    # otp
    await db.otp_verifications.create_index([("mobile", 1), ("purpose", 1)])
    await db.otp_verifications.create_index("created_at")
    # refresh tokens
    await db.refresh_tokens.create_index("jti", unique=True)
    await db.refresh_tokens.create_index("user_id")
    await db.refresh_tokens.create_index("expires_at")
    # audit logs
    await db.audit_logs.create_index("created_at")
    await db.audit_logs.create_index("actor_id")


async def seed_company_account() -> None:
    """Create the reserved RW000000 company membership if missing.

    This is the ROOT of the referral tree. It cannot be deleted or modified.
    """
    db = get_db()
    existing = await db.memberships.find_one({"membership_id": settings.COMPANY_MEMBERSHIP_ID})
    if existing:
        return
    now = datetime.now(timezone.utc).isoformat()
    await db.memberships.insert_one(
        {
            "membership_id": settings.COMPANY_MEMBERSHIP_ID,
            "owner_name": settings.COMPANY_NAME,
            "user_id": None,
            "sponsor_membership_id": None,
            "is_company": True,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )


async def seed_admin() -> None:
    db = get_db()
    existing = await db.admins.find_one({"mobile": settings.ADMIN_MOBILE})
    now = datetime.now(timezone.utc).isoformat()
    if not existing:
        await db.admins.insert_one(
            {
                "mobile": settings.ADMIN_MOBILE,
                "name": settings.ADMIN_NAME,
                "password_hash": hash_password(settings.ADMIN_PASSWORD),
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
        )
