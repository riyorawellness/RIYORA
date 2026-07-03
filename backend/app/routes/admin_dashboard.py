"""Rich admin dashboard — overview stats, top sellers, top referrers, feeds."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin
from app.models.phase7 import DashboardOverview

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])


def _iso_start_of_today() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _iso_start_of_month() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def _iso_start_of_year() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


async def _sum_revenue(db: AsyncIOMotorDatabase, since_iso: str) -> float:
    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "status": {"$in": ["active", "expired"]},
                "purchase_date": {"$gte": since_iso},
            }
        },
        {"$group": {"_id": None, "revenue": {"$sum": "$total"}}},
    ]
    async for r in db.program_purchases.aggregate(pipeline):
        return round(r["revenue"] or 0, 2)
    return 0.0


@router.get("/overview", response_model=DashboardOverview)
async def overview(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    total_users = await database.users.count_documents({"deleted_at": None})
    active_users = await database.users.count_documents({"deleted_at": None, "is_active": True})
    inactive_users = total_users - active_users
    today = await database.users.count_documents(
        {"deleted_at": None, "created_at": {"$gte": _iso_start_of_today()}}
    )
    total_programs = await database.programs.count_documents({"deleted_at": None, "is_active": True})
    total_purchases = await database.program_purchases.count_documents({"deleted_at": None})

    active_subs = await database.program_purchases.count_documents(
        {
            "deleted_at": None,
            "status": "active",
            "source": "subscription_mock",
            "expiry_date": {"$gt": now_iso},
        }
    )
    expired_subs = await database.program_purchases.count_documents(
        {
            "deleted_at": None,
            "source": "subscription_mock",
            "$or": [
                {"status": "expired"},
                {"expiry_date": {"$lte": now_iso}},
            ],
        }
    )

    pending_payout_amount = 0.0
    async for r in database.commissions.aggregate(
        [
            {"$match": {"status": "approved", "payout_id": None, "deleted_at": None}},
            {"$group": {"_id": None, "amount": {"$sum": "$amount"}}},
        ]
    ):
        pending_payout_amount = round(r["amount"] or 0, 2)

    paid_payout_amount = 0.0
    async for r in database.payouts.aggregate(
        [
            {"$match": {"status": "paid", "deleted_at": None}},
            {"$group": {"_id": None, "amount": {"$sum": "$amount"}}},
        ]
    ):
        paid_payout_amount = round(r["amount"] or 0, 2)

    pending_expiry = await database.program_purchases.count_documents(
        {
            "deleted_at": None,
            "status": "active",
            "expiry_date": {
                "$gte": now_iso,
                "$lte": (now + timedelta(days=7)).isoformat(),
            },
        }
    )

    return DashboardOverview(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        todays_registrations=today,
        total_programs=total_programs,
        total_purchases=total_purchases,
        active_subscribers=active_subs,
        expired_subscribers=expired_subs,
        pending_payout_amount=pending_payout_amount,
        paid_payout_amount=paid_payout_amount,
        pending_program_expiry=pending_expiry,
        revenue_today=await _sum_revenue(database, _iso_start_of_today()),
        revenue_month=await _sum_revenue(database, _iso_start_of_month()),
        revenue_year=await _sum_revenue(database, _iso_start_of_year()),
    )


@router.get("/revenue-series")
async def revenue_series(
    days: int = 30,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Daily revenue for the last N days."""
    days = max(1, min(days, 365))
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    since_iso = start.isoformat()

    pipeline = [
        {
            "$match": {
                "deleted_at": None,
                "status": {"$in": ["active", "expired"]},
                "purchase_date": {"$gte": since_iso},
            }
        },
        {
            "$group": {
                "_id": {"$substr": ["$purchase_date", 0, 10]},
                "revenue": {"$sum": "$total"},
                "count": {"$sum": 1},
            }
        },
    ]
    by_day: dict[str, dict] = {}
    async for r in database.program_purchases.aggregate(pipeline):
        by_day[r["_id"]] = {"revenue": round(r["revenue"] or 0, 2), "count": r["count"]}

    series = []
    for i in range(days):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        row = by_day.get(d) or {"revenue": 0, "count": 0}
        series.append({"date": d, "revenue": row["revenue"], "count": row["count"]})
    return {"days": days, "series": series}


@router.get("/top-programs")
async def top_programs(
    limit: int = 5,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    pipeline = [
        {"$match": {"deleted_at": None, "status": {"$in": ["active", "expired"]}}},
        {
            "$group": {
                "_id": "$program_id",
                "count": {"$sum": 1},
                "revenue": {"$sum": "$total"},
            }
        },
        {"$sort": {"revenue": -1}},
        {"$limit": max(1, min(limit, 20))},
    ]
    items = []
    async for r in database.program_purchases.aggregate(pipeline):
        prog = await database.programs.find_one({"id": r["_id"], "deleted_at": None}, {"name": 1, "thumbnail_url": 1})
        items.append(
            {
                "program_id": r["_id"],
                "name": (prog or {}).get("name") or "—",
                "thumbnail_url": (prog or {}).get("thumbnail_url"),
                "purchases": r["count"],
                "revenue": round(r["revenue"] or 0, 2),
            }
        )
    return {"items": items}


@router.get("/top-referrers")
async def top_referrers(
    limit: int = 5,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    pipeline = [
        {"$match": {"deleted_at": None, "status": {"$in": ["pending", "approved", "paid"]}}},
        {
            "$group": {
                "_id": "$sponsor_membership_id",
                "amount": {"$sum": "$amount"},
                "count": {"$sum": 1},
                "name": {"$first": "$sponsor_name"},
            }
        },
        {"$sort": {"amount": -1}},
        {"$limit": max(1, min(limit, 20))},
    ]
    items = []
    async for r in database.commissions.aggregate(pipeline):
        items.append(
            {
                "membership_id": r["_id"],
                "full_name": r.get("name") or "—",
                "commissions": r["count"],
                "amount": round(r["amount"] or 0, 2),
            }
        )
    return {"items": items}


@router.get("/recent-activity")
async def recent_activity(
    limit: int = 20,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    items = []
    async for r in (
        database.activity_log.find({}).sort("created_at", -1).limit(max(1, min(limit, 100)))
    ):
        r.pop("_id", None)
        items.append(r)
    return {"items": items}


@router.get("/recent-transactions")
async def recent_transactions(
    limit: int = 10,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    items = []
    async for p in (
        database.program_purchases.find({"deleted_at": None})
        .sort("purchase_date", -1)
        .limit(max(1, min(limit, 50)))
    ):
        p.pop("_id", None)
        u = await database.users.find_one(
            {"membership_id": p["user_membership_id"], "deleted_at": None},
            {"full_name": 1},
        )
        prog = await database.programs.find_one(
            {"id": p["program_id"], "deleted_at": None}, {"name": 1}
        )
        items.append(
            {
                "invoice_number": p.get("invoice_number"),
                "purchase_date": p.get("purchase_date"),
                "user_membership_id": p.get("user_membership_id"),
                "user_name": (u or {}).get("full_name"),
                "program_name": (prog or {}).get("name"),
                "total": p.get("total"),
                "status": p.get("status"),
            }
        )
    return {"items": items}
