"""Analytics API — admin + user endpoints powering Phase 8 dashboards.

Endpoints (admin, require admin token):
  GET  /api/analytics/kpis            → main financial KPIs (with comparison)
  GET  /api/analytics/revenue         → revenue series (day/week/month)
  GET  /api/analytics/programs       → program-wise breakdown
  GET  /api/analytics/states          → revenue by state
  GET  /api/analytics/user-growth     → new users per day
  GET  /api/analytics/commissions     → commission liability + level breakdown
  GET  /api/analytics/leaderboard     → top earners + top buyers
  GET  /api/analytics/subscriptions   → subscription health (active/expiring/expired + activity)
  GET  /api/analytics/gst             → GST collected in period
  GET  /api/analytics/dashboard       → convenience: everything at once

Endpoints (user):
  GET  /api/analytics/me              → personal analytics (earnings + downline + purchases)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.services import analytics as A
from app.services.commission_engine import summarise_user
from app.services.activity_meter import get_meter

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ---------- Admin -------------------------------------------------------------


@router.get("/kpis")
async def admin_kpis(
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    compare: bool = Query(default=True),
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    since_iso, until_iso = A.parse_range(since, until, default_days=30)
    curr = await A.revenue_summary(database, since_iso, until_iso)
    users = await A.user_kpis(database)
    payout = await A.payout_summary(database)
    commissions = await A.commission_summary(database, since_iso, until_iso)

    prev = None
    if compare:
        p_since, p_until = A.previous_range(since_iso, until_iso)
        prev = await A.revenue_summary(database, p_since, p_until)

    def _pct(new: float, old: float) -> float | None:
        if not old:
            return None
        return round(((new - old) / old) * 100, 2)

    net_margin = round(curr["revenue"] - commissions["total_liability"], 2)

    return {
        "range": {"since": since_iso, "until": until_iso},
        "revenue": curr,
        "revenue_previous": prev,
        "revenue_change_pct": _pct(curr["revenue"], (prev or {}).get("revenue", 0)) if prev else None,
        "users": users,
        "commissions": commissions,
        "payouts": payout,
        "net_margin": net_margin,
    }


@router.get("/revenue")
async def revenue_endpoint(
    since: str | None = None,
    until: str | None = None,
    granularity: str = Query(default="day", pattern=r"^(day|week|month)$"),
    program_id: str | None = None,
    compare: bool = True,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    since_iso, until_iso = A.parse_range(since, until, default_days=30)
    series = await A.revenue_series(database, since_iso, until_iso, granularity, program_id)
    prev_series = None
    if compare:
        p_since, p_until = A.previous_range(since_iso, until_iso)
        prev_series = await A.revenue_series(database, p_since, p_until, granularity, program_id)
    return {
        "range": {"since": since_iso, "until": until_iso},
        "granularity": granularity,
        "series": series,
        "previous_series": prev_series,
    }


@router.get("/programs")
async def program_analytics(
    since: str | None = None,
    until: str | None = None,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    since_iso, until_iso = A.parse_range(since, until, default_days=30)
    items = await A.program_mix(database, since_iso, until_iso)
    split = await A.source_split(database, since_iso, until_iso)
    return {"range": {"since": since_iso, "until": until_iso}, "items": items, "source_split": split}


@router.get("/states")
async def states_analytics(
    since: str | None = None,
    until: str | None = None,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    since_iso, until_iso = A.parse_range(since, until, default_days=30)
    items = await A.revenue_by_state(database, since_iso, until_iso)
    return {"range": {"since": since_iso, "until": until_iso}, "items": items}


@router.get("/user-growth")
async def user_growth_endpoint(
    since: str | None = None,
    until: str | None = None,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    since_iso, until_iso = A.parse_range(since, until, default_days=30)
    series = await A.user_growth(database, since_iso, until_iso)
    return {"range": {"since": since_iso, "until": until_iso}, "series": series}


@router.get("/commissions")
async def commissions_analytics(
    since: str | None = None,
    until: str | None = None,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    since_iso, until_iso = A.parse_range(since, until, default_days=30)
    summary = await A.commission_summary(database, since_iso, until_iso)
    by_level = await A.commissions_by_level(database, since_iso, until_iso)
    return {"range": {"since": since_iso, "until": until_iso}, "summary": summary, "by_level": by_level}


@router.get("/leaderboard")
async def leaderboard(
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    since_iso, until_iso = A.parse_range(since, until, default_days=30)
    earners = await A.top_earners(database, since_iso, until_iso, limit)
    buyers = await A.top_buyers(database, since_iso, until_iso, limit)
    return {
        "range": {"since": since_iso, "until": until_iso},
        "top_earners": earners,
        "top_buyers": buyers,
    }


@router.get("/subscriptions")
async def subscriptions_health(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    return await A.subscription_health(database)


@router.get("/gst")
async def gst_endpoint(
    since: str | None = None,
    until: str | None = None,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    since_iso, until_iso = A.parse_range(since, until, default_days=30)
    data = await A.gst_summary(database, since_iso, until_iso)
    return {"range": {"since": since_iso, "until": until_iso}, **data}


@router.get("/dashboard")
async def full_dashboard(
    since: str | None = None,
    until: str | None = None,
    granularity: str = Query(default="day", pattern=r"^(day|week|month)$"),
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Convenience: everything the analytics page needs in one call."""
    since_iso, until_iso = A.parse_range(since, until, default_days=30)
    p_since, p_until = A.previous_range(since_iso, until_iso)

    revenue = await A.revenue_summary(database, since_iso, until_iso)
    revenue_prev = await A.revenue_summary(database, p_since, p_until)
    r_series = await A.revenue_series(database, since_iso, until_iso, granularity)
    r_series_prev = await A.revenue_series(database, p_since, p_until, granularity)
    users_growth = await A.user_growth(database, since_iso, until_iso)
    programs = await A.program_mix(database, since_iso, until_iso)
    states = await A.revenue_by_state(database, since_iso, until_iso)
    commissions = await A.commission_summary(database, since_iso, until_iso)
    by_level = await A.commissions_by_level(database, since_iso, until_iso)
    subs = await A.subscription_health(database)
    gst = await A.gst_summary(database, since_iso, until_iso)
    payouts = await A.payout_summary(database)
    earners = await A.top_earners(database, since_iso, until_iso, 5)
    buyers = await A.top_buyers(database, since_iso, until_iso, 5)
    user_kpi = await A.user_kpis(database)

    net_margin = round(revenue["revenue"] - commissions["total_liability"], 2)

    def _pct(new: float, old: float):
        if not old:
            return None
        return round(((new - old) / old) * 100, 2)

    return {
        "range": {"since": since_iso, "until": until_iso},
        "granularity": granularity,
        "kpis": {
            "revenue": revenue,
            "revenue_previous": revenue_prev,
            "revenue_change_pct": _pct(revenue["revenue"], revenue_prev["revenue"]),
            "users": user_kpi,
            "net_margin": net_margin,
        },
        "revenue_series": r_series,
        "revenue_series_previous": r_series_prev,
        "user_growth": users_growth,
        "programs": programs,
        "states": states,
        "commissions": {"summary": commissions, "by_level": by_level},
        "subscriptions": subs,
        "gst": gst,
        "payouts": payouts,
        "leaderboard": {"top_earners": earners, "top_buyers": buyers},
    }


# ---------- User -------------------------------------------------------------


@router.get("/me")
async def user_personal_analytics(
    since: str | None = None,
    until: str | None = None,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    mid = current["membership_id"]
    since_iso, until_iso = A.parse_range(since, until, default_days=90)

    earnings_series = await A.user_earnings_series(database, mid, since_iso, until_iso)
    downline_series = await A.user_downline_growth(database, mid, since_iso, until_iso)
    summary = await summarise_user(database, mid)
    meter = await get_meter(database, mid)

    # Downline totals (3 levels)
    counts = {"L1": 0, "L2": 0, "L3": 0}
    ids = [mid]
    for lvl in (1, 2, 3):
        next_ids = []
        async for d in database.referral_tree.find(
            {"sponsor_membership_id": {"$in": ids}, "deleted_at": None},
            {"user_membership_id": 1},
        ):
            counts[f"L{lvl}"] += 1
            next_ids.append(d["user_membership_id"])
        ids = next_ids

    # Purchases in range
    purchases_agg = database.program_purchases.aggregate(
        [
            {
                "$match": {
                    "user_membership_id": mid,
                    "deleted_at": None,
                    "purchase_date": {"$gte": since_iso, "$lte": until_iso},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "spent": {"$sum": "$total"},
                    "count": {"$sum": 1},
                }
            },
        ]
    )
    spent = {"amount": 0.0, "count": 0}
    async for r in purchases_agg:
        spent = {"amount": round(r["spent"] or 0, 2), "count": r["count"]}

    return {
        "range": {"since": since_iso, "until": until_iso},
        "earnings": summary,
        "earnings_series": earnings_series,
        "downline_series": downline_series,
        "downline_counts": counts,
        "activity_meter": meter,
        "spent": spent,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
