"""User report data builders — feed into shared exports service.

Returns (columns, rows, summary_lines) per report type. Used both for PDF (legacy),
CSV, and Excel exports.
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.commission_engine import summarise_user


async def build_user_report(
    db: AsyncIOMotorDatabase, user: dict, report_type: str
) -> tuple[list[dict], list[dict], list[str]]:
    """Return (columns, rows, summary_lines) for the given user report."""
    mid = user["membership_id"]

    if report_type == "income":
        summary = await summarise_user(db, mid)
        columns = [
            {"key": "created_at",    "label": "Date",     "width": 14, "type": "date"},
            {"key": "program_name",  "label": "Program",  "width": 22},
            {"key": "buyer",         "label": "Buyer",    "width": 22},
            {"key": "level",         "label": "Level",    "width": 8, "type": "int"},
            {"key": "amount",        "label": "Amount",   "width": 12, "type": "money"},
            {"key": "status",        "label": "Status",   "width": 12},
        ]
        rows = []
        async for c in db.commissions.find(
            {"sponsor_membership_id": mid, "deleted_at": None}
        ).sort("created_at", -1).limit(1000):
            rows.append(
                {
                    "created_at": c.get("created_at"),
                    "program_name": c.get("program_name"),
                    "buyer": f"{c.get('buyer_name','—')} ({c.get('buyer_membership_id','')})",
                    "level": c.get("level"),
                    "amount": c.get("amount"),
                    "status": (c.get("status") or "").capitalize(),
                }
            )
        summary_lines = [
            f"Lifetime earnings: Rs. {summary['lifetime']:,.2f}",
            f"Pending: Rs. {summary['pending']:,.2f} · Approved: Rs. {summary['approved']:,.2f} · Paid: Rs. {summary['paid']:,.2f} · Rejected: Rs. {summary['rejected']:,.2f}",
            f"This month: Rs. {summary['current_month']:,.2f}",
        ]
        return columns, rows, summary_lines

    if report_type in ("referral", "downline"):
        columns = [
            {"key": "membership_id", "label": "Membership ID", "width": 15},
            {"key": "full_name",     "label": "Name",           "width": 22},
            {"key": "level",         "label": "Level",          "width": 8},
            {"key": "joining_date",  "label": "Joined",         "width": 14, "type": "date"},
            {"key": "status",        "label": "Status",         "width": 12},
        ]
        rows: list[dict] = []
        current_level = [mid]
        depth = 0
        while current_level and depth < 3:
            level_ids: list[str] = []
            async for d in db.referral_tree.find(
                {"sponsor_membership_id": {"$in": current_level}, "deleted_at": None}
            ):
                m = await db.memberships.find_one({"membership_id": d["user_membership_id"]}, {"owner_name": 1}) or {}
                rows.append(
                    {
                        "membership_id": d["user_membership_id"],
                        "full_name": m.get("owner_name") or "—",
                        "level": f"L{depth + 1}",
                        "joining_date": d.get("joining_date"),
                        "status": (d.get("status") or "active").capitalize(),
                    }
                )
                level_ids.append(d["user_membership_id"])
            current_level = level_ids
            depth += 1
        summary_lines = [f"Total downline members: {len(rows)}"]
        return columns, rows, summary_lines

    if report_type == "subscription":
        columns = [
            {"key": "purchase_date", "label": "Cycle Start", "width": 14, "type": "date"},
            {"key": "expiry_date",   "label": "Cycle End",   "width": 14, "type": "date"},
            {"key": "status",        "label": "Status",      "width": 12},
            {"key": "sessions",      "label": "Sessions",    "width": 10, "type": "int"},
            {"key": "payment_status","label": "Payment",     "width": 12},
            {"key": "total",         "label": "Total",       "width": 12, "type": "money"},
        ]
        rows = []
        async for p in db.program_purchases.find(
            {
                "user_membership_id": mid,
                "deleted_at": None,
                "$or": [{"subscription_id": {"$ne": None}}, {"source": "subscription_mock"}],
            }
        ).sort("purchase_date", -1):
            sessions = await db.activity_sessions.count_documents(
                {"subscription_purchase_id": p["id"], "deleted_at": None}
            )
            rows.append(
                {
                    "purchase_date": p.get("purchase_date"),
                    "expiry_date": p.get("expiry_date"),
                    "status": (p.get("status") or "").capitalize(),
                    "sessions": sessions,
                    "payment_status": p.get("payment_status", "captured"),
                    "total": p.get("total"),
                }
            )
        return columns, rows, [f"Cycles: {len(rows)}"]

    if report_type == "transaction":
        columns = [
            {"key": "purchase_date", "label": "Date",       "width": 14, "type": "date"},
            {"key": "invoice_number","label": "Invoice",    "width": 18},
            {"key": "program_name",  "label": "Program",    "width": 22},
            {"key": "taxable_amount","label": "Taxable",    "width": 12, "type": "money"},
            {"key": "gst_amount",    "label": "GST",        "width": 10, "type": "money"},
            {"key": "total",         "label": "Total",      "width": 12, "type": "money"},
            {"key": "status",        "label": "Status",     "width": 10},
        ]
        rows = []
        grand = 0.0
        async for p in db.program_purchases.find(
            {"user_membership_id": mid, "deleted_at": None}
        ).sort("purchase_date", -1):
            prog = await db.programs.find_one({"id": p["program_id"]}, {"name": 1}) or {}
            rows.append(
                {
                    "purchase_date": p.get("purchase_date"),
                    "invoice_number": p.get("invoice_number"),
                    "program_name": prog.get("name"),
                    "taxable_amount": p.get("taxable_amount") or p.get("price_paid"),
                    "gst_amount": p.get("gst_amount"),
                    "total": p.get("total"),
                    "status": (p.get("status") or "").capitalize(),
                }
            )
            grand += float(p.get("total") or 0)
        return columns, rows, [f"Total spent: Rs. {grand:,.2f}", f"Transactions: {len(rows)}"]

    raise ValueError(f"Unknown report type: {report_type}")
