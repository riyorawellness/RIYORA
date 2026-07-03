"""Admin Reports — detailed tabular reports with filters + CSV/Excel/PDF export.

Report types:
    users        — user roster
    programs     — program catalog + sales
    subscriptions— active/expired subscriptions
    payments     — all purchases (Razorpay transactions)
    referrals    — commission ledger
    activity     — logged sessions
    assessments  — assessment results

Query params (common):
    since, until   ISO datetime (defaults last 90 days)
    q              free-text search
    status         filter
    program_id     filter (where applicable)
    state          filter (users only)
    level          filter (referrals only)
    page, page_size

Export endpoints:
    GET /admin/reports/{report_type}         → JSON (paginated)
    GET /admin/reports/{report_type}/export  → file (?format=csv|excel|pdf)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin
from app.services.analytics import parse_range
from app.services.exports import export_table
from app.utils.audit import log_action

router = APIRouter(prefix="/admin/reports", tags=["Admin Reports"])


# ---------- Column definitions per report type -------------------------------


COLUMNS: dict[str, list[dict]] = {
    "users": [
        {"key": "membership_id", "label": "Membership ID", "width": 18},
        {"key": "full_name",     "label": "Name",          "width": 24},
        {"key": "mobile",        "label": "Mobile",        "width": 15},
        {"key": "state",         "label": "State",         "width": 15},
        {"key": "city",          "label": "City",          "width": 15},
        {"key": "sponsor_membership_id", "label": "Sponsor", "width": 15},
        {"key": "status",        "label": "Status",        "width": 12},
        {"key": "created_at",    "label": "Joined",        "width": 15, "type": "date"},
    ],
    "programs": [
        {"key": "name",          "label": "Program",       "width": 26},
        {"key": "level",         "label": "Level",         "width": 8},
        {"key": "price",         "label": "Price",         "width": 12, "type": "money"},
        {"key": "purchases",     "label": "Sales",         "width": 10, "type": "int"},
        {"key": "revenue",       "label": "Revenue",       "width": 14, "type": "money"},
        {"key": "is_active",     "label": "Active",        "width": 8, "type": "bool"},
    ],
    "subscriptions": [
        {"key": "user_membership_id", "label": "Member",    "width": 15},
        {"key": "user_name",     "label": "Name",           "width": 22},
        {"key": "program_name",  "label": "Program",        "width": 20},
        {"key": "plan",          "label": "Plan",           "width": 10},
        {"key": "purchase_date", "label": "Started",        "width": 14, "type": "date"},
        {"key": "expiry_date",   "label": "Expires",        "width": 14, "type": "date"},
        {"key": "status",        "label": "Status",         "width": 12},
        {"key": "total",         "label": "Amount",         "width": 12, "type": "money"},
    ],
    "payments": [
        {"key": "invoice_number","label": "Invoice",        "width": 18},
        {"key": "purchase_date", "label": "Date",           "width": 14, "type": "date"},
        {"key": "user_membership_id", "label": "Member",    "width": 14},
        {"key": "user_name",     "label": "Name",           "width": 20},
        {"key": "program_name",  "label": "Program",        "width": 20},
        {"key": "taxable_amount","label": "Taxable",        "width": 12, "type": "money"},
        {"key": "gst_amount",    "label": "GST",            "width": 10, "type": "money"},
        {"key": "total",         "label": "Total",          "width": 12, "type": "money"},
        {"key": "status",        "label": "Status",         "width": 10},
    ],
    "referrals": [
        {"key": "created_at",    "label": "Date",           "width": 14, "type": "date"},
        {"key": "buyer_membership_id", "label": "Buyer",    "width": 14},
        {"key": "buyer_name",    "label": "Buyer Name",     "width": 20},
        {"key": "sponsor_membership_id", "label": "Sponsor","width": 14},
        {"key": "sponsor_name",  "label": "Sponsor Name",   "width": 20},
        {"key": "program_name",  "label": "Program",        "width": 18},
        {"key": "level",         "label": "Level",          "width": 8, "type": "int"},
        {"key": "amount",        "label": "Amount",         "width": 12, "type": "money"},
        {"key": "status",        "label": "Status",         "width": 10},
    ],
    "activity": [
        {"key": "completed_at",  "label": "Time",           "width": 18, "type": "datetime"},
        {"key": "user_membership_id", "label": "Member",    "width": 14},
        {"key": "user_name",     "label": "Name",           "width": 22},
        {"key": "program_id",    "label": "Program",        "width": 22},
        {"key": "source",        "label": "Source",         "width": 14},
        {"key": "valid_for_cycle","label": "In cycle",      "width": 10, "type": "bool"},
    ],
    "assessments": [
        {"key": "created_at",    "label": "Attempted",      "width": 16, "type": "datetime"},
        {"key": "user_membership_id", "label": "Member",    "width": 14},
        {"key": "user_name",     "label": "Name",           "width": 22},
        {"key": "assessment_id", "label": "Assessment",     "width": 22},
        {"key": "score",         "label": "Score",          "width": 10, "type": "int"},
        {"key": "max_score",     "label": "Max",            "width": 8, "type": "int"},
        {"key": "passed",        "label": "Passed",         "width": 10, "type": "bool"},
    ],
}


# ---------- Query builders ---------------------------------------------------


async def _build_users(database: AsyncIOMotorDatabase, filters: dict) -> tuple[int, list[dict]]:
    match: dict = {"deleted_at": None}
    if filters.get("since") and filters.get("until"):
        match["created_at"] = {"$gte": filters["since"], "$lte": filters["until"]}
    if filters.get("state"):
        match["state"] = filters["state"]
    if filters.get("status") == "active":
        match["is_active"] = True
    elif filters.get("status") in ("suspended", "deactivated"):
        match["status"] = filters["status"]
    if filters.get("q"):
        q = filters["q"]
        match["$or"] = [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"mobile": {"$regex": q}},
            {"membership_id": {"$regex": q, "$options": "i"}},
        ]
    total = await database.users.count_documents(match)
    cursor = database.users.find(match).sort("created_at", -1)
    if filters.get("page_size"):
        cursor = cursor.skip((filters["page"] - 1) * filters["page_size"]).limit(filters["page_size"])
    items = []
    async for u in cursor:
        items.append(
            {
                "membership_id": u.get("membership_id"),
                "full_name": u.get("full_name"),
                "mobile": u.get("mobile"),
                "state": u.get("state"),
                "city": u.get("city"),
                "sponsor_membership_id": u.get("sponsor_membership_id"),
                "status": u.get("status", "active" if u.get("is_active", True) else "deactivated"),
                "created_at": u.get("created_at"),
            }
        )
    return total, items


async def _build_programs(database: AsyncIOMotorDatabase, filters: dict) -> tuple[int, list[dict]]:
    match: dict = {"deleted_at": None}
    if filters.get("q"):
        match["name"] = {"$regex": filters["q"], "$options": "i"}
    if filters.get("status") == "active":
        match["is_active"] = True
    elif filters.get("status") == "inactive":
        match["is_active"] = False
    total = await database.programs.count_documents(match)
    cursor = database.programs.find(match).sort("order_index", 1)
    if filters.get("page_size"):
        cursor = cursor.skip((filters["page"] - 1) * filters["page_size"]).limit(filters["page_size"])
    since = filters.get("since") or "1970-01-01"
    until = filters.get("until") or "9999-12-31"
    items = []
    async for p in cursor:
        # sales aggregates
        agg = database.program_purchases.aggregate(
            [
                {"$match": {"program_id": p["id"], "deleted_at": None,
                            "status": {"$in": ["active", "expired"]},
                            "purchase_date": {"$gte": since, "$lte": until}}},
                {"$group": {"_id": None, "count": {"$sum": 1}, "revenue": {"$sum": "$total"}}},
            ]
        )
        row = {"purchases": 0, "revenue": 0.0}
        async for r in agg:
            row = {"purchases": r["count"], "revenue": round(r["revenue"] or 0, 2)}
        items.append(
            {
                "id": p["id"],
                "name": p.get("name"),
                "level": p.get("level"),
                "price": p.get("price"),
                "is_active": p.get("is_active", True),
                **row,
            }
        )
    return total, items


async def _build_subscriptions(database: AsyncIOMotorDatabase, filters: dict) -> tuple[int, list[dict]]:
    match: dict = {
        "deleted_at": None,
        "$or": [{"source": "subscription_mock"}, {"subscription_id": {"$ne": None}}],
    }
    if filters.get("since") and filters.get("until"):
        match["purchase_date"] = {"$gte": filters["since"], "$lte": filters["until"]}
    if filters.get("status"):
        match["status"] = filters["status"]
    if filters.get("q"):
        match["user_membership_id"] = {"$regex": filters["q"], "$options": "i"}
    total = await database.program_purchases.count_documents(match)
    cursor = database.program_purchases.find(match).sort("purchase_date", -1)
    if filters.get("page_size"):
        cursor = cursor.skip((filters["page"] - 1) * filters["page_size"]).limit(filters["page_size"])
    items = []
    async for s in cursor:
        u = await database.users.find_one({"membership_id": s["user_membership_id"]}, {"full_name": 1}) or {}
        prog = await database.programs.find_one({"id": s["program_id"]}, {"name": 1}) or {}
        items.append(
            {
                "user_membership_id": s["user_membership_id"],
                "user_name": u.get("full_name"),
                "program_name": prog.get("name"),
                "plan": s.get("plan") or s.get("subscription_plan") or "—",
                "purchase_date": s.get("purchase_date"),
                "expiry_date": s.get("expiry_date"),
                "status": s.get("status"),
                "total": s.get("total"),
            }
        )
    return total, items


async def _build_payments(database: AsyncIOMotorDatabase, filters: dict) -> tuple[int, list[dict]]:
    match: dict = {"deleted_at": None}
    if filters.get("since") and filters.get("until"):
        match["purchase_date"] = {"$gte": filters["since"], "$lte": filters["until"]}
    if filters.get("status"):
        match["status"] = filters["status"]
    if filters.get("program_id"):
        match["program_id"] = filters["program_id"]
    if filters.get("q"):
        q = filters["q"]
        match["$or"] = [
            {"invoice_number": {"$regex": q, "$options": "i"}},
            {"user_membership_id": {"$regex": q, "$options": "i"}},
        ]
    total = await database.program_purchases.count_documents(match)
    cursor = database.program_purchases.find(match).sort("purchase_date", -1)
    if filters.get("page_size"):
        cursor = cursor.skip((filters["page"] - 1) * filters["page_size"]).limit(filters["page_size"])
    items = []
    async for p in cursor:
        u = await database.users.find_one({"membership_id": p["user_membership_id"]}, {"full_name": 1}) or {}
        prog = await database.programs.find_one({"id": p["program_id"]}, {"name": 1}) or {}
        items.append(
            {
                "invoice_number": p.get("invoice_number"),
                "purchase_date": p.get("purchase_date"),
                "user_membership_id": p["user_membership_id"],
                "user_name": u.get("full_name"),
                "program_name": prog.get("name"),
                "taxable_amount": p.get("taxable_amount") or p.get("price_paid"),
                "gst_amount": p.get("gst_amount"),
                "total": p.get("total"),
                "status": p.get("status"),
            }
        )
    return total, items


async def _build_referrals(database: AsyncIOMotorDatabase, filters: dict) -> tuple[int, list[dict]]:
    match: dict = {"deleted_at": None}
    if filters.get("since") and filters.get("until"):
        match["created_at"] = {"$gte": filters["since"], "$lte": filters["until"]}
    if filters.get("status"):
        match["status"] = filters["status"]
    if filters.get("level"):
        match["level"] = int(filters["level"])
    if filters.get("q"):
        q = filters["q"]
        match["$or"] = [
            {"buyer_membership_id": {"$regex": q, "$options": "i"}},
            {"sponsor_membership_id": {"$regex": q, "$options": "i"}},
            {"sponsor_name": {"$regex": q, "$options": "i"}},
        ]
    total = await database.commissions.count_documents(match)
    cursor = database.commissions.find(match).sort("created_at", -1)
    if filters.get("page_size"):
        cursor = cursor.skip((filters["page"] - 1) * filters["page_size"]).limit(filters["page_size"])
    items = []
    async for c in cursor:
        items.append(
            {
                "created_at": c.get("created_at"),
                "buyer_membership_id": c.get("buyer_membership_id"),
                "buyer_name": c.get("buyer_name"),
                "sponsor_membership_id": c.get("sponsor_membership_id"),
                "sponsor_name": c.get("sponsor_name"),
                "program_name": c.get("program_name"),
                "level": c.get("level"),
                "amount": c.get("amount"),
                "status": c.get("status"),
            }
        )
    return total, items


async def _build_activity(database: AsyncIOMotorDatabase, filters: dict) -> tuple[int, list[dict]]:
    match: dict = {"deleted_at": None}
    if filters.get("since") and filters.get("until"):
        match["completed_at"] = {"$gte": filters["since"], "$lte": filters["until"]}
    if filters.get("q"):
        match["user_membership_id"] = {"$regex": filters["q"], "$options": "i"}
    total = await database.activity_sessions.count_documents(match)
    cursor = database.activity_sessions.find(match).sort("completed_at", -1)
    if filters.get("page_size"):
        cursor = cursor.skip((filters["page"] - 1) * filters["page_size"]).limit(filters["page_size"])
    items = []
    async for a in cursor:
        u = await database.users.find_one({"membership_id": a["user_membership_id"]}, {"full_name": 1}) or {}
        items.append(
            {
                "completed_at": a.get("completed_at"),
                "user_membership_id": a.get("user_membership_id"),
                "user_name": u.get("full_name"),
                "program_id": a.get("program_id"),
                "source": a.get("source"),
                "valid_for_cycle": a.get("valid_for_cycle", True),
            }
        )
    return total, items


async def _build_assessments(database: AsyncIOMotorDatabase, filters: dict) -> tuple[int, list[dict]]:
    match: dict = {"deleted_at": None}
    if filters.get("since") and filters.get("until"):
        match["created_at"] = {"$gte": filters["since"], "$lte": filters["until"]}
    if filters.get("q"):
        match["user_membership_id"] = {"$regex": filters["q"], "$options": "i"}
    total = await database.assessment_results.count_documents(match)
    cursor = database.assessment_results.find(match).sort("created_at", -1)
    if filters.get("page_size"):
        cursor = cursor.skip((filters["page"] - 1) * filters["page_size"]).limit(filters["page_size"])
    items = []
    async for a in cursor:
        u = await database.users.find_one({"membership_id": a["user_membership_id"]}, {"full_name": 1}) or {}
        items.append(
            {
                "created_at": a.get("created_at"),
                "user_membership_id": a.get("user_membership_id"),
                "user_name": u.get("full_name"),
                "assessment_id": a.get("assessment_id"),
                "score": a.get("score"),
                "max_score": a.get("max_score") or a.get("total"),
                "passed": a.get("passed"),
            }
        )
    return total, items


BUILDERS = {
    "users": _build_users,
    "programs": _build_programs,
    "subscriptions": _build_subscriptions,
    "payments": _build_payments,
    "referrals": _build_referrals,
    "activity": _build_activity,
    "assessments": _build_assessments,
}


def _collect_filters(
    since: str | None,
    until: str | None,
    q: str | None,
    status: str | None,
    program_id: str | None,
    state: str | None,
    level: int | None,
    page: int,
    page_size: int,
) -> dict:
    since_iso, until_iso = parse_range(since, until, default_days=90)
    return {
        "since": since_iso,
        "until": until_iso,
        "q": q,
        "status": status,
        "program_id": program_id,
        "state": state,
        "level": level,
        "page": page,
        "page_size": page_size,
    }


# ---------- Endpoints --------------------------------------------------------


@router.get("/{report_type}")
async def list_report(
    report_type: str,
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    q: str | None = None,
    status: str | None = None,
    program_id: str | None = None,
    state: str | None = None,
    level: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    if report_type not in BUILDERS:
        raise HTTPException(400, f"Unknown report type. Allowed: {sorted(BUILDERS.keys())}")
    filters = _collect_filters(since, until, q, status, program_id, state, level, page, page_size)
    total, items = await BUILDERS[report_type](database, filters)
    return {
        "report_type": report_type,
        "columns": COLUMNS[report_type],
        "range": {"since": filters["since"], "until": filters["until"]},
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


@router.get("/{report_type}/export")
async def export_report(
    report_type: str,
    fmt: str = Query(default="csv", pattern=r"^(csv|excel|pdf)$"),
    since: str | None = None,
    until: str | None = None,
    q: str | None = None,
    status: str | None = None,
    program_id: str | None = None,
    state: str | None = None,
    level: int | None = None,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    if report_type not in BUILDERS:
        raise HTTPException(400, f"Unknown report type. Allowed: {sorted(BUILDERS.keys())}")
    filters = _collect_filters(since, until, q, status, program_id, state, level, page=1, page_size=0)
    # Full dataset (no pagination) — cap at 20k rows for safety
    filters["page"] = 1
    filters["page_size"] = 0
    _, items = await BUILDERS[report_type](database, filters)
    if len(items) > 20000:
        items = items[:20000]

    title_map = {
        "users": "User Report",
        "programs": "Programs Report",
        "subscriptions": "Subscriptions Report",
        "payments": "Payments Report",
        "referrals": "Referrals Report",
        "activity": "Activity Report",
        "assessments": "Assessments Report",
    }
    subtitle = f"Period: {filters['since'][:10]} → {filters['until'][:10]}"
    content, media_type, filename = export_table(
        fmt,
        columns=COLUMNS[report_type],
        rows=items,
        title=title_map[report_type],
        filename_stem=f"riyora-{report_type}-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        subtitle=subtitle,
    )
    await log_action(
        database,
        actor_id=admin["mobile"],
        action=f"report.export.{report_type}.{fmt}",
        entity="report",
        meta={"count": len(items), "filters": {k: v for k, v in filters.items() if v}},
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
