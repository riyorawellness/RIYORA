"""Analytics aggregation service — MongoDB pipelines for admin dashboard.

All functions accept a `db` handle and an optional `since_iso` / `until_iso`
date range (ISO 8601 strings, UTC). If not provided, sensible defaults are used.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def parse_range(since: str | None, until: str | None, default_days: int = 30) -> tuple[str, str]:
    """Return (since_iso, until_iso). Defaults: last `default_days` days ending today."""
    if until:
        u = datetime.fromisoformat(until.replace("Z", "+00:00"))
    else:
        u = _now()
    if since:
        s = datetime.fromisoformat(since.replace("Z", "+00:00"))
    else:
        s = u - timedelta(days=default_days - 1)
    s = s.replace(hour=0, minute=0, second=0, microsecond=0)
    u = u.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return _iso(s), _iso(u)


def previous_range(since_iso: str, until_iso: str) -> tuple[str, str]:
    """Return the immediately preceding period of equal length."""
    s = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    u = datetime.fromisoformat(until_iso.replace("Z", "+00:00"))
    span = u - s
    prev_u = s - timedelta(microseconds=1)
    prev_s = prev_u - span
    return _iso(prev_s), _iso(prev_u)


# ---------- Revenue -----------------------------------------------------------


async def revenue_summary(
    db: AsyncIOMotorDatabase,
    since_iso: str,
    until_iso: str,
    program_id: str | None = None,
    state: str | None = None,
) -> dict:
    match: dict[str, Any] = {
        "deleted_at": None,
        "status": {"$in": ["active", "expired"]},
        "purchase_date": {"$gte": since_iso, "$lte": until_iso},
    }
    if program_id:
        match["program_id"] = program_id
    if state:
        # State is on user, not purchase — resolve via lookup
        member_ids = [u["membership_id"] async for u in db.users.find({"state": state, "deleted_at": None}, {"membership_id": 1})]
        match["user_membership_id"] = {"$in": member_ids or ["__none__"]}

    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": None,
                "revenue": {"$sum": "$total"},
                "taxable": {"$sum": {"$ifNull": ["$taxable_amount", "$price_paid"]}},
                "gst": {"$sum": "$gst_amount"},
                "count": {"$sum": 1},
                "avg_ticket": {"$avg": "$total"},
            }
        },
    ]
    async for r in db.program_purchases.aggregate(pipeline):
        return {
            "revenue": round(r["revenue"] or 0, 2),
            "taxable": round(r["taxable"] or 0, 2),
            "gst": round(r["gst"] or 0, 2),
            "count": r["count"] or 0,
            "avg_ticket": round(r["avg_ticket"] or 0, 2),
        }
    return {"revenue": 0.0, "taxable": 0.0, "gst": 0.0, "count": 0, "avg_ticket": 0.0}


async def revenue_series(
    db: AsyncIOMotorDatabase,
    since_iso: str,
    until_iso: str,
    granularity: str = "day",  # day | week | month
    program_id: str | None = None,
) -> list[dict]:
    match: dict[str, Any] = {
        "deleted_at": None,
        "status": {"$in": ["active", "expired"]},
        "purchase_date": {"$gte": since_iso, "$lte": until_iso},
    }
    if program_id:
        match["program_id"] = program_id

    if granularity == "month":
        key_expr = {"$substr": ["$purchase_date", 0, 7]}
    elif granularity == "week":
        # ISO week via $isoWeek (parse date str)
        key_expr = {
            "$dateToString": {
                "format": "%G-W%V",
                "date": {"$dateFromString": {"dateString": "$purchase_date"}},
            }
        }
    else:
        key_expr = {"$substr": ["$purchase_date", 0, 10]}

    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": key_expr,
                "revenue": {"$sum": "$total"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    out: list[dict] = []
    async for r in db.program_purchases.aggregate(pipeline):
        out.append({"bucket": r["_id"], "revenue": round(r["revenue"] or 0, 2), "count": r["count"]})
    return out


# ---------- Program mix / breakdowns ------------------------------------------


async def program_mix(db: AsyncIOMotorDatabase, since_iso: str, until_iso: str) -> list[dict]:
    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "status": {"$in": ["active", "expired"]},
                "purchase_date": {"$gte": since_iso, "$lte": until_iso},
            }
        },
        {
            "$group": {
                "_id": "$program_id",
                "revenue": {"$sum": "$total"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"revenue": -1}},
    ]
    items = []
    async for r in db.program_purchases.aggregate(pipeline):
        prog = await db.programs.find_one({"id": r["_id"]}, {"name": 1, "level": 1}) or {}
        items.append(
            {
                "program_id": r["_id"],
                "name": prog.get("name") or "—",
                "level": prog.get("level"),
                "revenue": round(r["revenue"] or 0, 2),
                "count": r["count"],
            }
        )
    return items


async def revenue_by_state(db: AsyncIOMotorDatabase, since_iso: str, until_iso: str) -> list[dict]:
    # Purchases don't carry state — resolve via user_membership_id.
    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "status": {"$in": ["active", "expired"]},
                "purchase_date": {"$gte": since_iso, "$lte": until_iso},
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "user_membership_id",
                "foreignField": "membership_id",
                "as": "u",
            }
        },
        {"$unwind": {"path": "$u", "preserveNullAndEmptyArrays": True}},
        {
            "$group": {
                "_id": {"$ifNull": ["$u.state", "Unknown"]},
                "revenue": {"$sum": "$total"},
                "count": {"$sum": 1},
                "users": {"$addToSet": "$user_membership_id"},
            }
        },
        {"$sort": {"revenue": -1}},
        {"$limit": 30},
    ]
    out = []
    async for r in db.program_purchases.aggregate(pipeline):
        out.append(
            {
                "state": r["_id"] or "Unknown",
                "revenue": round(r["revenue"] or 0, 2),
                "count": r["count"],
                "users": len(r.get("users") or []),
            }
        )
    return out


async def source_split(db: AsyncIOMotorDatabase, since_iso: str, until_iso: str) -> list[dict]:
    """Program vs Subscription split."""
    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "status": {"$in": ["active", "expired"]},
                "purchase_date": {"$gte": since_iso, "$lte": until_iso},
            }
        },
        {
            "$group": {
                "_id": {"$ifNull": ["$source", "razorpay"]},
                "revenue": {"$sum": "$total"},
                "count": {"$sum": 1},
            }
        },
    ]
    out = []
    async for r in db.program_purchases.aggregate(pipeline):
        out.append({"source": r["_id"], "revenue": round(r["revenue"] or 0, 2), "count": r["count"]})
    return out


# ---------- Users -------------------------------------------------------------


async def user_growth(db: AsyncIOMotorDatabase, since_iso: str, until_iso: str) -> list[dict]:
    pipeline = [
        {"$match": {"deleted_at": None, "created_at": {"$gte": since_iso, "$lte": until_iso}}},
        {"$group": {"_id": {"$substr": ["$created_at", 0, 10]}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    out = []
    async for r in db.users.aggregate(pipeline):
        out.append({"bucket": r["_id"], "count": r["count"]})
    return out


async def user_kpis(db: AsyncIOMotorDatabase) -> dict:
    now_iso = _iso(_now())
    total = await db.users.count_documents({"deleted_at": None})
    active = await db.users.count_documents({"deleted_at": None, "is_active": True})
    # Active subscribers = has any active subscription purchase
    active_subs = await db.program_purchases.count_documents(
        {
            "deleted_at": None,
            "status": "active",
            "$or": [
                {"source": "subscription_mock"},
                {"subscription_id": {"$ne": None}},
            ],
            "expiry_date": {"$gt": now_iso},
        }
    )
    return {"total": total, "active": active, "active_subscribers": active_subs}


# ---------- Commissions -------------------------------------------------------


async def commission_summary(
    db: AsyncIOMotorDatabase, since_iso: str, until_iso: str
) -> dict:
    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "created_at": {"$gte": since_iso, "$lte": until_iso},
            }
        },
        {
            "$group": {
                "_id": "$status",
                "amount": {"$sum": "$amount"},
                "count": {"$sum": 1},
            }
        },
    ]
    out = {"pending": 0.0, "approved": 0.0, "paid": 0.0, "rejected": 0.0, "counts": {}}
    async for r in db.commissions.aggregate(pipeline):
        st = r["_id"] or "unknown"
        out[st] = round(r["amount"] or 0, 2)
        out["counts"][st] = r["count"]
    out["total_liability"] = round(out.get("pending", 0) + out.get("approved", 0), 2)
    return out


async def commissions_by_level(
    db: AsyncIOMotorDatabase, since_iso: str, until_iso: str
) -> list[dict]:
    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "created_at": {"$gte": since_iso, "$lte": until_iso},
                "status": {"$in": ["pending", "approved", "paid"]},
            }
        },
        {
            "$group": {
                "_id": {"level": "$level", "status": "$status"},
                "amount": {"$sum": "$amount"},
                "count": {"$sum": 1},
            }
        },
    ]
    grid: dict[int, dict] = {}
    async for r in db.commissions.aggregate(pipeline):
        lvl = r["_id"]["level"]
        st = r["_id"]["status"]
        grid.setdefault(lvl, {"level": lvl, "pending": 0, "approved": 0, "paid": 0, "count": 0})
        grid[lvl][st] = round(r["amount"] or 0, 2)
        grid[lvl]["count"] += r["count"]
    return [grid[k] for k in sorted(grid.keys())]


async def top_earners(
    db: AsyncIOMotorDatabase, since_iso: str, until_iso: str, limit: int = 10
) -> list[dict]:
    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "created_at": {"$gte": since_iso, "$lte": until_iso},
                "status": {"$in": ["pending", "approved", "paid"]},
            }
        },
        {
            "$group": {
                "_id": "$sponsor_membership_id",
                "amount": {"$sum": "$amount"},
                "count": {"$sum": 1},
                "name": {"$first": "$sponsor_name"},
            }
        },
        {"$sort": {"amount": -1}},
        {"$limit": limit},
    ]
    out = []
    async for r in db.commissions.aggregate(pipeline):
        out.append(
            {
                "membership_id": r["_id"],
                "full_name": r.get("name") or "—",
                "amount": round(r["amount"] or 0, 2),
                "count": r["count"],
            }
        )
    return out


async def top_buyers(
    db: AsyncIOMotorDatabase, since_iso: str, until_iso: str, limit: int = 10
) -> list[dict]:
    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "purchase_date": {"$gte": since_iso, "$lte": until_iso},
                "status": {"$in": ["active", "expired"]},
            }
        },
        {
            "$group": {
                "_id": "$user_membership_id",
                "amount": {"$sum": "$total"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"amount": -1}},
        {"$limit": limit},
    ]
    out = []
    async for r in db.program_purchases.aggregate(pipeline):
        u = await db.users.find_one({"membership_id": r["_id"]}, {"full_name": 1, "state": 1}) or {}
        out.append(
            {
                "membership_id": r["_id"],
                "full_name": u.get("full_name") or "—",
                "state": u.get("state"),
                "amount": round(r["amount"] or 0, 2),
                "count": r["count"],
            }
        )
    return out


# ---------- Subscription health ----------------------------------------------


async def subscription_health(db: AsyncIOMotorDatabase) -> dict:
    now_iso = _iso(_now())
    week_iso = _iso(_now() + timedelta(days=7))

    active = await db.program_purchases.count_documents(
        {"deleted_at": None, "status": "active", "expiry_date": {"$gt": now_iso},
         "$or": [{"source": "subscription_mock"}, {"subscription_id": {"$ne": None}}]}
    )
    expiring = await db.program_purchases.count_documents(
        {"deleted_at": None, "status": "active", "expiry_date": {"$gte": now_iso, "$lte": week_iso},
         "$or": [{"source": "subscription_mock"}, {"subscription_id": {"$ne": None}}]}
    )
    expired = await db.program_purchases.count_documents(
        {"deleted_at": None, "expiry_date": {"$lte": now_iso},
         "$or": [{"source": "subscription_mock"}, {"subscription_id": {"$ne": None}}]}
    )
    # Activity meter breakdown across ALL active subscribers
    pipeline = [
        {
            "$match": {
                "deleted_at": None, "status": "active",
                "expiry_date": {"$gt": now_iso},
                "$or": [{"source": "subscription_mock"}, {"subscription_id": {"$ne": None}}],
            }
        },
        {"$group": {"_id": "$user_membership_id"}},
    ]
    active_mids: list[str] = []
    async for r in db.program_purchases.aggregate(pipeline):
        active_mids.append(r["_id"])

    # session counts by member
    sess_counts: dict[str, int] = {}
    if active_mids:
        pipeline2 = [
            {"$match": {"user_membership_id": {"$in": active_mids}, "deleted_at": None,
                        "valid_for_cycle": True}},
            {"$group": {"_id": "$user_membership_id", "n": {"$sum": 1}}},
        ]
        async for r in db.activity_sessions.aggregate(pipeline2):
            sess_counts[r["_id"]] = r["n"]

    required = 4
    green = sum(1 for m in active_mids if sess_counts.get(m, 0) >= required)
    yellow = sum(1 for m in active_mids if 0 < sess_counts.get(m, 0) < required)
    red = sum(1 for m in active_mids if sess_counts.get(m, 0) == 0)

    return {
        "active": active,
        "expiring_7d": expiring,
        "expired": expired,
        "activity": {"green": green, "yellow": yellow, "red": red},
    }


# ---------- GST / Payout ------------------------------------------------------


async def gst_summary(
    db: AsyncIOMotorDatabase, since_iso: str, until_iso: str
) -> dict:
    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "status": {"$in": ["active", "expired"]},
                "purchase_date": {"$gte": since_iso, "$lte": until_iso},
            }
        },
        {
            "$group": {
                "_id": None,
                "taxable": {"$sum": {"$ifNull": ["$taxable_amount", "$price_paid"]}},
                "gst": {"$sum": "$gst_amount"},
                "total": {"$sum": "$total"},
                "count": {"$sum": 1},
            }
        },
    ]
    async for r in db.program_purchases.aggregate(pipeline):
        return {
            "taxable": round(r["taxable"] or 0, 2),
            "gst": round(r["gst"] or 0, 2),
            "total": round(r["total"] or 0, 2),
            "count": r["count"] or 0,
        }
    return {"taxable": 0.0, "gst": 0.0, "total": 0.0, "count": 0}


async def payout_summary(db: AsyncIOMotorDatabase) -> dict:
    out = {"pending_amount": 0.0, "paid_amount": 0.0, "pending_count": 0, "paid_count": 0}
    async for r in db.commissions.aggregate(
        [
            {"$match": {"status": "approved", "payout_id": None, "deleted_at": None}},
            {"$group": {"_id": None, "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        ]
    ):
        out["pending_amount"] = round(r["amount"] or 0, 2)
        out["pending_count"] = r["count"] or 0
    async for r in db.payouts.aggregate(
        [
            {"$match": {"status": "paid", "deleted_at": None}},
            {"$group": {"_id": None, "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        ]
    ):
        out["paid_amount"] = round(r["amount"] or 0, 2)
        out["paid_count"] = r["count"] or 0
    return out


# ---------- User personal analytics -------------------------------------------


async def user_earnings_series(
    db: AsyncIOMotorDatabase, membership_id: str, since_iso: str, until_iso: str
) -> list[dict]:
    pipeline = [
        {
            "$match": {
                "sponsor_membership_id": membership_id,
                "deleted_at": None,
                "status": {"$in": ["pending", "approved", "paid"]},
                "created_at": {"$gte": since_iso, "$lte": until_iso},
            }
        },
        {"$group": {"_id": {"$substr": ["$created_at", 0, 10]}, "amount": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    out = []
    async for r in db.commissions.aggregate(pipeline):
        out.append({"bucket": r["_id"], "amount": round(r["amount"] or 0, 2), "count": r["count"]})
    return out


async def user_downline_growth(
    db: AsyncIOMotorDatabase, membership_id: str, since_iso: str, until_iso: str
) -> list[dict]:
    # Direct L1 members joined in range
    pipeline = [
        {
            "$match": {
                "sponsor_membership_id": membership_id,
                "deleted_at": None,
                "joining_date": {"$gte": since_iso, "$lte": until_iso},
            }
        },
        {"$group": {"_id": {"$substr": ["$joining_date", 0, 10]}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    out = []
    async for r in db.referral_tree.aggregate(pipeline):
        out.append({"bucket": r["_id"], "count": r["count"]})
    return out
