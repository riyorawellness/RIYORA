"""Admin Danger Zone — Empty App Data + Hard delete user (soft).

These endpoints are irreversible. All calls require:
  - Admin JWT.
  - A body-typed confirmation string that MUST equal the exact literal
    the frontend guides the admin to type (server-side hard gate).

Empty App Data preserves:
  - The admin account itself.
  - The company / referral-root membership (RW000000).
  - All CMS content (programs, modules, categories, banners, policies,
    QR payment settings, system settings).

Empty App Data wipes:
  - All non-admin users + memberships.
  - Referral tree rows (except company row).
  - Profiles, purchases, progress, assessment results, certificates.
  - Notifications + templates, OTP records, refresh tokens, audit logs.
  - Commissions, payouts, bank details, subscriptions.
  - Manual-payment requests + payment orders.
  - Login lockouts + activity sessions.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.deps import db, get_current_admin
from app.utils.audit import log_action

router = APIRouter(prefix="/admin/danger", tags=["Admin Danger Zone"])
settings = get_settings()

EMPTY_CONFIRM_PHRASE = "EMPTY APP DATA"
DELETE_USER_CONFIRM_PHRASE = "DELETE USER"


class EmptyAppDataRequest(BaseModel):
    confirmation: str = Field(..., description=f'Must equal "{EMPTY_CONFIRM_PHRASE}"')


class DeleteUserRequest(BaseModel):
    confirmation: str = Field(..., description=f'Must equal "{DELETE_USER_CONFIRM_PHRASE}"')


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Collections cleared wholesale (all documents removed).
_WIPE_ALL = [
    "profiles",
    "program_purchases",
    "program_progress",
    "assessment_results",
    "certificates",
    "notifications",
    "notification_templates",
    "otp_verifications",
    "refresh_tokens",
    "audit_logs",
    "activity_log",
    "activity_sessions",
    "commissions",
    "payouts",
    "bank_details",
    "subscriptions",
    "payment_orders",
    "payment_requests",
    "user_settings",
    "login_lockouts",
]


@router.post("/empty-app-data")
async def empty_app_data(
    body: EmptyAppDataRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    if body.confirmation.strip() != EMPTY_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f'Confirmation phrase must be exactly "{EMPTY_CONFIRM_PHRASE}".',
        )

    company_id = settings.COMPANY_MEMBERSHIP_ID
    admin_mobile = admin["mobile"]

    report: dict[str, int] = {}

    # Wipe user accounts EXCEPT admins.
    r = await database.users.delete_many({"role": {"$ne": "admin"}})
    report["users"] = r.deleted_count

    # Wipe memberships EXCEPT the company root.
    r = await database.memberships.delete_many(
        {"membership_id": {"$ne": company_id}, "is_company": {"$ne": True}}
    )
    report["memberships"] = r.deleted_count

    # Wipe referral tree EXCEPT company (if it has a row).
    r = await database.referral_tree.delete_many(
        {"user_membership_id": {"$ne": company_id}}
    )
    report["referral_tree"] = r.deleted_count

    # Wipe every collection listed above wholesale.
    for coll in _WIPE_ALL:
        r = await database[coll].delete_many({})
        report[coll] = r.deleted_count

    await log_action(
        database,
        actor_id=admin_mobile,
        action="danger.empty_app_data",
        entity="system",
        meta=report,
    )

    return {
        "success": True,
        "message": "App data cleared. Admin, company account, and content preserved.",
        "cleared": report,
    }


@router.delete("/users/{membership_id}")
async def soft_delete_user(
    membership_id: str,
    body: DeleteUserRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    """Soft-delete a user.

    - User row: ``deleted_at`` stamped, ``is_active=false``, mobile suffixed
      so the number is freed for re-signup.
    - Membership row: soft-deleted (referral tree preserved so sponsor
      lineage of downline users stays intact).
    - Sessions: all refresh tokens revoked.
    """
    if body.confirmation.strip() != DELETE_USER_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f'Confirmation phrase must be exactly "{DELETE_USER_CONFIRM_PHRASE}".',
        )

    if membership_id == settings.COMPANY_MEMBERSHIP_ID:
        raise HTTPException(status_code=400, detail="Cannot delete the company root account.")

    user = await database.users.find_one({"membership_id": membership_id, "deleted_at": None})
    if not user:
        raise HTTPException(status_code=404, detail="User not found or already deleted.")

    if user.get("role") == "admin":
        raise HTTPException(status_code=400, detail="Admin accounts cannot be deleted here.")

    now = _iso()
    freed_mobile = user["mobile"]
    parked_mobile = f"{freed_mobile}#deleted-{int(datetime.now(timezone.utc).timestamp())}"

    await database.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "deleted_at": now,
                "is_active": False,
                "status": "deleted",
                "mobile": parked_mobile,
                "original_mobile": freed_mobile,
                "updated_at": now,
            }
        },
    )

    await database.memberships.update_one(
        {"membership_id": membership_id, "deleted_at": None},
        {"$set": {"deleted_at": now, "is_active": False, "updated_at": now}},
    )

    await database.refresh_tokens.update_many(
        {"user_id": membership_id}, {"$set": {"revoked": True}}
    )

    await log_action(
        database,
        actor_id=admin["mobile"],
        action="danger.delete_user",
        entity="user",
        entity_id=membership_id,
        meta={"freed_mobile": freed_mobile},
    )

    return {
        "success": True,
        "message": f"User {membership_id} deleted. Mobile {freed_mobile} freed for re-signup.",
    }
