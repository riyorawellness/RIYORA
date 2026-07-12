"""Commission Engine — 3-level referral commissions.

Called by the payment engine after a purchase is verified. Walks up the
referral tree 3 levels; for each sponsor, checks eligibility via
`activity_meter.is_eligible_for_commission` and creates a `commissions` row
with status='pending'. Ineligible sponsors get a row with status='rejected'
so the reason is auditable and the buyer's downline is transparent.

Commission calculation:
    percent mode → amount = round(total * pct / 100, 2)
    fixed  mode → amount = fixed
    both   mode → amount = fixed + round(total * pct / 100, 2)

Per-program override (program.commission_override) takes precedence over
global app_settings. Global fallbacks come from app_settings, then env.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.services.activity_meter import is_eligible_for_commission

settings = get_settings()


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_setting(db: AsyncIOMotorDatabase, key: str, default: Any) -> Any:
    row = await db.app_settings.find_one({"key": key, "deleted_at": None})
    if not row:
        return default
    return row.get("value", default)


async def _global_rates(db: AsyncIOMotorDatabase) -> dict:
    return {
        "mode": await _get_setting(db, "commission_mode", "percent"),
        "l1_percent": float(await _get_setting(db, "commission_l1_percent", settings.COMMISSION_L1_PERCENT)),
        "l2_percent": float(await _get_setting(db, "commission_l2_percent", settings.COMMISSION_L2_PERCENT)),
        "l3_percent": float(await _get_setting(db, "commission_l3_percent", settings.COMMISSION_L3_PERCENT)),
        "l1_fixed": float(await _get_setting(db, "commission_l1_fixed", 0)),
        "l2_fixed": float(await _get_setting(db, "commission_l2_fixed", 0)),
        "l3_fixed": float(await _get_setting(db, "commission_l3_fixed", 0)),
    }


def _amount_for_level(rates: dict, level: int, total: float) -> float:
    mode = rates.get("mode", "percent")
    pct = float(rates.get(f"l{level}_percent", 0) or 0)
    fixed = float(rates.get(f"l{level}_fixed", 0) or 0)
    if mode == "fixed":
        return round(fixed, 2)
    if mode == "both":
        return round(fixed + total * pct / 100.0, 2)
    return round(total * pct / 100.0, 2)


async def _resolve_rates(db: AsyncIOMotorDatabase, program: dict) -> dict:
    override = program.get("commission_override") or {}
    rates = await _global_rates(db)
    # Override any field explicitly set on the program.
    for k in (
        "mode",
        "l1_percent",
        "l2_percent",
        "l3_percent",
        "l1_fixed",
        "l2_fixed",
        "l3_fixed",
    ):
        v = override.get(k)
        if v is not None:
            rates[k] = v
    return rates


async def _upline_chain(
    db: AsyncIOMotorDatabase, membership_id: str, max_levels: int = 3
) -> list[dict]:
    """Return up to `max_levels` sponsors above the given member (excluding company root)."""
    chain: list[dict] = []
    node = await db.referral_tree.find_one(
        {"user_membership_id": membership_id, "deleted_at": None}
    )
    depth = 0
    while node and depth < max_levels:
        sponsor_id = node.get("sponsor_membership_id")
        if not sponsor_id:
            break
        sponsor_node = await db.referral_tree.find_one(
            {"user_membership_id": sponsor_id, "deleted_at": None}
        )
        if not sponsor_node:
            break
        # Skip the reserved company root — company shouldn't receive commissions on itself.
        if sponsor_id == settings.COMPANY_MEMBERSHIP_ID:
            break
        chain.append({"membership_id": sponsor_id, "level": depth + 1})
        node = sponsor_node
        depth += 1
    return chain


async def create_commissions_for_purchase(
    db: AsyncIOMotorDatabase, purchase: dict
) -> list[dict]:
    """Create commission ledger rows for a completed purchase (idempotent per level)."""
    # Dummy (tester) purchases never trigger commissions.
    if purchase.get("is_dummy") or purchase.get("source") == "dummy":
        return []
    program = await db.programs.find_one(
        {"id": purchase["program_id"], "deleted_at": None}
    ) or {}
    program.pop("_id", None)
    rates = await _resolve_rates(db, program)
    total = float(purchase.get("total") or 0)
    if total <= 0:
        return []

    buyer_id = purchase["user_membership_id"]
    chain = await _upline_chain(db, buyer_id, max_levels=3)

    created: list[dict] = []
    for sponsor in chain:
        level = sponsor["level"]
        sponsor_id = sponsor["membership_id"]
        # Idempotency guard.
        dup = await db.commissions.find_one(
            {"purchase_id": purchase["id"], "sponsor_membership_id": sponsor_id, "deleted_at": None}
        )
        if dup:
            continue

        amount = _amount_for_level(rates, level, total)
        if amount <= 0:
            continue

        eligible = await is_eligible_for_commission(db, sponsor_id)
        buyer = await db.users.find_one({"membership_id": buyer_id}, {"full_name": 1}) or {}
        sponsor_user = await db.users.find_one({"membership_id": sponsor_id}, {"full_name": 1}) or {}

        doc = {
            "id": str(uuid.uuid4()),
            "purchase_id": purchase["id"],
            "program_id": purchase["program_id"],
            "program_name": program.get("name"),
            "purchase_source": purchase.get("source", "razorpay"),
            "purchase_amount": total,
            "buyer_membership_id": buyer_id,
            "buyer_name": buyer.get("full_name"),
            "sponsor_membership_id": sponsor_id,
            "sponsor_name": sponsor_user.get("full_name"),
            "level": level,
            "amount": amount,
            "status": "pending" if eligible else "rejected",
            "reason": None if eligible else "Sponsor not active (Inner Peace / activity requirement not met)",
            "created_at": _iso(),
            "updated_at": _iso(),
            "approved_at": None,
            "paid_at": None,
            "rejected_at": None if eligible else _iso(),
            "payout_id": None,
            "deleted_at": None,
        }
        await db.commissions.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc)

        # Notify sponsor of new referral income (only when it's actually payable)
        if eligible:
            try:
                from app.services.notify import referral_income as _notify_ref
                await _notify_ref(
                    db,
                    sponsor_mid=sponsor_id,
                    buyer_name=buyer.get("full_name") or "a member",
                    amount=amount,
                    level=level,
                )
            except Exception:  # noqa: BLE001
                pass
    return created


async def summarise_user(db: AsyncIOMotorDatabase, membership_id: str) -> dict:
    """Aggregate earnings for the given member."""
    pipeline = [
        {"$match": {"sponsor_membership_id": membership_id, "deleted_at": None}},
        {"$group": {"_id": "$status", "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    out = {
        "pending": {"amount": 0.0, "count": 0},
        "approved": {"amount": 0.0, "count": 0},
        "paid": {"amount": 0.0, "count": 0},
        "rejected": {"amount": 0.0, "count": 0},
    }
    async for row in db.commissions.aggregate(pipeline):
        out.setdefault(row["_id"] or "unknown", {"amount": 0.0, "count": 0})
        out[row["_id"] or "unknown"] = {
            "amount": round(row["amount"] or 0, 2),
            "count": row["count"],
        }

    lifetime = round(
        out["pending"]["amount"] + out["approved"]["amount"] + out["paid"]["amount"], 2
    )
    total_pending_payout = round(out["approved"]["amount"], 2)

    # Current month earnings (any status except rejected).
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_pipeline = [
        {
            "$match": {
                "sponsor_membership_id": membership_id,
                "status": {"$ne": "rejected"},
                "created_at": {"$gte": month_start},
                "deleted_at": None,
            }
        },
        {"$group": {"_id": None, "amount": {"$sum": "$amount"}}},
    ]
    cm = 0.0
    async for row in db.commissions.aggregate(month_pipeline):
        cm = round(row["amount"] or 0, 2)

    return {
        "lifetime": lifetime,
        "pending": out["pending"]["amount"],
        "approved": total_pending_payout,
        "paid": out["paid"]["amount"],
        "rejected": out["rejected"]["amount"],
        "current_month": cm,
        "counts": {k: v["count"] for k, v in out.items()},
    }
