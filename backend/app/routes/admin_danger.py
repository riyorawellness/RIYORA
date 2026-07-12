"""Admin Danger Zone — Empty App Data + Hard delete user (soft) + Backups.

These endpoints are irreversible. All destructive calls require:
  - Admin JWT.
  - A body-typed confirmation string that MUST equal the exact literal
    the frontend guides the admin to type (server-side hard gate).
  - The admin's current password (double-check against session hijack).

Empty App Data automatically creates a full mongodump backup BEFORE wiping,
so a restore is always available via `POST /admin/backups/{name}/restore`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.deps import db, get_current_admin
from app.core.security import verify_password
from app.services import backup as backup_svc
from app.utils.audit import log_action

router = APIRouter(prefix="/admin/danger", tags=["Admin Danger Zone"])
settings = get_settings()

EMPTY_CONFIRM_PHRASE = "EMPTY APP DATA"
DELETE_USER_CONFIRM_PHRASE = "DELETE USER"


class EmptyAppDataRequest(BaseModel):
    confirmation: str = Field(..., description=f'Must equal "{EMPTY_CONFIRM_PHRASE}"')
    admin_password: str = Field(..., description="Current admin password for defense-in-depth")


class DeleteUserRequest(BaseModel):
    confirmation: str = Field(..., description=f'Must equal "{DELETE_USER_CONFIRM_PHRASE}"')
    admin_password: str | None = Field(default=None, description="Current admin password (required for destructive scopes)")
    # Optional: granular data-scope removal. If any of these are True, the
    # corresponding data is HARD-deleted (removed permanently). The core
    # user + membership rows are always SOFT-deleted so the referral tree
    # keeps working for downline sponsors.
    wipe_purchases: bool = False        # program_purchases + program_progress
    wipe_notifications: bool = True     # notifications for this user
    wipe_certificates: bool = False     # certificates issued
    wipe_assessments: bool = False      # assessment_results
    wipe_bank_details: bool = False     # bank_details
    wipe_commissions: bool = False      # commissions earned by them (destructive — affects payout history)
    wipe_referral_tree: bool = False    # referral_tree row (destructive — breaks downline lineage)
    wipe_profile: bool = True           # profiles row


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

    # Password double-check — protect against XSS/CSRF hijacking a live admin
    # session. Verify against the fresh DB row, not the JWT payload.
    fresh = await database.admins.find_one(
        {"mobile": admin["mobile"], "deleted_at": None}
    )
    if not fresh or not verify_password(body.admin_password, fresh.get("password_hash", "")):
        raise HTTPException(status_code=403, detail="Admin password is incorrect")

    # Auto-backup BEFORE wiping. If the backup fails we abort to prevent
    # unrecoverable data loss.
    try:
        backup_meta = await backup_svc.create_backup(reason="pre_empty_app_data")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Automatic backup failed — wipe aborted. {e}",
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
        meta={"cleared": report, "backup": backup_meta},
    )

    return {
        "success": True,
        "message": "App data cleared. Admin, company account, and content preserved.",
        "cleared": report,
        "backup": backup_meta,
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

    # If any destructive scope is enabled, require the admin password.
    destructive = (
        body.wipe_commissions
        or body.wipe_referral_tree
        or body.wipe_purchases
        or body.wipe_certificates
    )
    if destructive:
        if not body.admin_password:
            raise HTTPException(
                status_code=403,
                detail="Admin password required for destructive delete scopes.",
            )
        fresh = await database.admins.find_one(
            {"mobile": admin["mobile"], "deleted_at": None}
        )
        if not fresh or not verify_password(
            body.admin_password, fresh.get("password_hash", "")
        ):
            raise HTTPException(status_code=403, detail="Admin password is incorrect")

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

    # Granular hard-deletes based on admin's checkbox selections.
    wiped: dict[str, int] = {}
    if body.wipe_profile:
        r = await database.profiles.delete_many({"user_membership_id": membership_id})
        wiped["profiles"] = r.deleted_count
    if body.wipe_purchases:
        r = await database.program_purchases.delete_many({"user_membership_id": membership_id})
        wiped["program_purchases"] = r.deleted_count
        r = await database.program_progress.delete_many({"user_membership_id": membership_id})
        wiped["program_progress"] = r.deleted_count
        r = await database.payment_requests.delete_many({"user_membership_id": membership_id})
        wiped["payment_requests"] = r.deleted_count
        r = await database.payment_orders.delete_many({"user_membership_id": membership_id})
        wiped["payment_orders"] = r.deleted_count
    if body.wipe_notifications:
        r = await database.notifications.delete_many({"user_membership_id": membership_id})
        wiped["notifications"] = r.deleted_count
    if body.wipe_certificates:
        r = await database.certificates.delete_many({"user_membership_id": membership_id})
        wiped["certificates"] = r.deleted_count
    if body.wipe_assessments:
        r = await database.assessment_results.delete_many({"user_membership_id": membership_id})
        wiped["assessment_results"] = r.deleted_count
    if body.wipe_bank_details:
        r = await database.bank_details.delete_many({"user_membership_id": membership_id})
        wiped["bank_details"] = r.deleted_count
    if body.wipe_commissions:
        r = await database.commissions.delete_many({"beneficiary_membership_id": membership_id})
        wiped["commissions"] = r.deleted_count
        r = await database.payouts.delete_many({"user_membership_id": membership_id})
        wiped["payouts"] = r.deleted_count
    if body.wipe_referral_tree:
        r = await database.referral_tree.delete_many({"user_membership_id": membership_id})
        wiped["referral_tree"] = r.deleted_count

    await log_action(
        database,
        actor_id=admin["mobile"],
        action="danger.delete_user",
        entity="user",
        entity_id=membership_id,
        meta={"freed_mobile": freed_mobile, "wiped": wiped},
    )

    return {
        "success": True,
        "message": f"User {membership_id} deleted. Mobile {freed_mobile} freed for re-signup.",
        "wiped": wiped,
    }
