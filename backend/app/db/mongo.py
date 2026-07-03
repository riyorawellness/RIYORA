"""MongoDB client singleton, index setup and seed logic.

Using MongoDB as PostgreSQL fallback per spec. Collections mirror the tables
listed in the requirements: users, admins, profiles, memberships,
otp_verifications, refresh_tokens, settings, notifications, audit_logs.
"""
from datetime import datetime, timezone
import uuid

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

    # ----- Phase 2 -----
    await db.profiles.create_index("user_membership_id", unique=True)
    await db.program_categories.create_index("slug", unique=True)
    await db.program_categories.create_index("order_index")
    await db.programs.create_index("slug", unique=True)
    await db.programs.create_index("category_id")
    await db.programs.create_index("is_active")
    await db.programs.create_index("order_index")
    await db.program_modules.create_index([("program_id", 1), ("module_number", 1)], unique=True)
    await db.program_modules.create_index("order_index")
    await db.program_purchases.create_index([("user_membership_id", 1), ("program_id", 1)])
    await db.program_purchases.create_index("invoice_number", unique=True)
    await db.program_purchases.create_index("expiry_date")
    await db.program_progress.create_index(
        [("user_membership_id", 1), ("program_id", 1)], unique=True
    )
    await db.assessments.create_index("module_id", unique=True)
    await db.assessments.create_index("program_id")
    await db.assessment_results.create_index([("user_membership_id", 1), ("assessment_id", 1)])
    await db.certificates.create_index("certificate_number", unique=True)
    await db.certificates.create_index([("user_membership_id", 1), ("program_id", 1)])
    await db.referral_tree.create_index("user_membership_id", unique=True)
    await db.referral_tree.create_index("sponsor_membership_id")
    await db.referral_tree.create_index("level")
    await db.bank_details.create_index("user_membership_id", unique=True)
    await db.user_settings.create_index([("user_membership_id", 1), ("key", 1)], unique=True)
    await db.app_settings.create_index("key", unique=True)
    await db.system_configuration.create_index("key", unique=True)
    await db.notifications.create_index([("user_membership_id", 1), ("created_at", -1)])
    await db.notifications.create_index("is_broadcast")
    await db.activity_log.create_index("actor_membership_id")
    await db.activity_log.create_index("created_at")

    # ----- Phase 5 (Payments) -----
    await db.payment_orders.create_index("order_id", unique=True)
    await db.payment_orders.create_index([("user_membership_id", 1), ("created_at", -1)])
    await db.payment_orders.create_index("status")
    await db.subscriptions.create_index("subscription_id", unique=True)
    await db.subscriptions.create_index([("user_membership_id", 1), ("status", 1)])
    # razorpay_payment_id may be null; sparse index to keep uniqueness only when set
    await db.program_purchases.create_index("razorpay_payment_id", sparse=True)


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
    from app.core.security import verify_password  # local import to avoid cycle

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
    elif not verify_password(settings.ADMIN_PASSWORD, existing["password_hash"]):
        await db.admins.update_one(
            {"_id": existing["_id"]},
            {"$set": {"password_hash": hash_password(settings.ADMIN_PASSWORD), "updated_at": now}},
        )


_DEFAULT_CATEGORIES = [
    {"name": "Foundation", "slug": "foundation", "order_index": 1,
     "description": "Beginner-friendly wellness practices."},
    {"name": "Subscription", "slug": "subscription", "order_index": 2,
     "description": "Recurring programs like Inner Peace."},
    {"name": "Advanced", "slug": "advanced", "order_index": 3,
     "description": "Progressive spiritual growth (Levels 1-5)."},
    {"name": "Special", "slug": "special", "order_index": 4,
     "description": "Workshops, retreats and limited offerings."},
]

_DEFAULT_APP_SETTINGS = [
    {"key": "default_gst_percent", "value": 18, "description": "Default GST % applied to purchases"},
    {"key": "default_validity_days", "value": 365, "description": "Default program validity in days"},
    {"key": "activity_sessions_required", "value": 4, "description": "Sessions required per cycle"},
    {"key": "commission_l1_percent", "value": 10, "description": "Referral commission L1 (%)"},
    {"key": "commission_l2_percent", "value": 5, "description": "Referral commission L2 (%)"},
    {"key": "commission_l3_percent", "value": 2, "description": "Referral commission L3 (%)"},
    {"key": "support_email", "value": "care@riyorawellness.com", "description": "Support email"},
    {"key": "support_phone", "value": "+91-9999999999", "description": "Support phone"},
    {"key": "app_version", "value": "1.0.0", "description": "Current app version"},
]


async def seed_program_categories() -> None:
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    for c in _DEFAULT_CATEGORIES:
        await db.program_categories.update_one(
            {"slug": c["slug"]},
            {
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    **c,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "deleted_at": None,
                }
            },
            upsert=True,
        )
    # Backfill: any legacy rows without `id` get one assigned.
    async for legacy in db.program_categories.find({"id": {"$exists": False}}):
        await db.program_categories.update_one(
            {"_id": legacy["_id"]}, {"$set": {"id": str(uuid.uuid4())}}
        )


async def seed_app_settings() -> None:
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    for s in _DEFAULT_APP_SETTINGS:
        await db.app_settings.update_one(
            {"key": s["key"]},
            {
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    **s,
                    "created_at": now,
                    "updated_at": now,
                    "deleted_at": None,
                }
            },
            upsert=True,
        )
    async for legacy in db.app_settings.find({"id": {"$exists": False}}):
        await db.app_settings.update_one(
            {"_id": legacy["_id"]}, {"$set": {"id": str(uuid.uuid4())}}
        )


async def seed_referral_tree_root() -> None:
    """Ensure the company root exists in referral_tree collection as level 0."""
    db = get_db()
    if await db.referral_tree.find_one({"user_membership_id": settings.COMPANY_MEMBERSHIP_ID}):
        return
    now = datetime.now(timezone.utc).isoformat()
    await db.referral_tree.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_membership_id": settings.COMPANY_MEMBERSHIP_ID,
            "sponsor_membership_id": None,
            "level": 0,
            "joining_date": now,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
    )
