"""User 360° — comprehensive per-user report.

Collects every piece of user activity into a JSON payload and an Excel
workbook with one sheet per section. Sections match the pre-launch spec:
  Profile · Sponsor · Team · Referrals · Payments · Programs (progress) ·
  Validity · Wallet · Commissions · Activity · Login History · Subscriptions
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.exports import to_excel_multi_sheet
from app.services.activity_meter import get_meter


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- column definitions per sheet ------------------------------------------
COLUMNS: dict[str, list[dict]] = {
    "Profile": [
        {"key": "field", "label": "Field", "width": 24},
        {"key": "value", "label": "Value", "width": 60},
    ],
    "Downline": [
        {"key": "membership_id", "label": "Membership ID", "width": 16},
        {"key": "full_name",     "label": "Name",          "width": 24},
        {"key": "mobile",        "label": "Mobile",        "width": 14},
        {"key": "level",         "label": "Level",         "width": 8, "type": "int"},
        {"key": "created_at",    "label": "Joined",        "width": 22, "type": "date"},
        {"key": "is_active",     "label": "Active",        "width": 10, "type": "bool"},
    ],
    "Payments": [
        {"key": "invoice_number","label": "Invoice",       "width": 22},
        {"key": "purchase_date", "label": "Date",          "width": 22, "type": "date"},
        {"key": "program_name",  "label": "Program",       "width": 30},
        {"key": "source",        "label": "Payment via",   "width": 14},
        {"key": "taxable_amount","label": "Taxable",       "width": 12, "type": "money"},
        {"key": "gst_amount",    "label": "GST",           "width": 10, "type": "money"},
        {"key": "total",         "label": "Total",         "width": 12, "type": "money"},
        {"key": "utr",           "label": "UTR",           "width": 16},
        {"key": "razorpay_payment_id", "label": "RZP Pay ID", "width": 20},
        {"key": "status",        "label": "Status",        "width": 10},
    ],
    "Programs": [
        {"key": "program_name",       "label": "Program",       "width": 30},
        {"key": "purchase_date",      "label": "Purchased",     "width": 22, "type": "date"},
        {"key": "expiry_date",        "label": "Expires",       "width": 22, "type": "date"},
        {"key": "completed_modules",  "label": "Modules done",  "width": 12, "type": "int"},
        {"key": "total_modules",      "label": "Modules total", "width": 12, "type": "int"},
        {"key": "percentage",         "label": "Progress %",    "width": 12, "type": "int"},
        {"key": "certificate_number", "label": "Certificate",   "width": 24},
    ],
    "Commissions": [
        {"key": "created_at",     "label": "Date",              "width": 22, "type": "date"},
        {"key": "buyer_name",     "label": "Buyer",             "width": 22},
        {"key": "program_name",   "label": "Program",           "width": 24},
        {"key": "level",          "label": "Level",             "width": 8, "type": "int"},
        {"key": "amount",         "label": "Amount",            "width": 12, "type": "money"},
        {"key": "status",         "label": "Status",            "width": 12},
    ],
    "Activity": [
        {"key": "completed_at",   "label": "Time",              "width": 22, "type": "datetime"},
        {"key": "source",         "label": "Source",            "width": 14},
        {"key": "program_id",     "label": "Program",           "width": 22},
        {"key": "module_id",      "label": "Module",            "width": 22},
    ],
    "Logins": [
        {"key": "created_at",     "label": "When",              "width": 22, "type": "datetime"},
        {"key": "action",         "label": "Event",             "width": 20},
        {"key": "entity_id",      "label": "Detail",            "width": 24},
    ],
    "Payouts": [
        {"key": "created_at",     "label": "Requested",         "width": 22, "type": "date"},
        {"key": "amount",         "label": "Amount",            "width": 12, "type": "money"},
        {"key": "status",         "label": "Status",            "width": 12},
        {"key": "utr",            "label": "UTR",               "width": 20},
        {"key": "paid_at",        "label": "Paid on",           "width": 22, "type": "date"},
    ],
}


async def _first(cursor):
    async for x in cursor:
        return x
    return None


async def collect_user_360(
    db: AsyncIOMotorDatabase, membership_id: str
) -> dict[str, Any]:
    user = await db.users.find_one(
        {"membership_id": membership_id, "deleted_at": None}
    )
    if not user:
        return {}
    user.pop("_id", None)
    user.pop("password_hash", None)

    # Sponsor
    sponsor = None
    if user.get("sponsor_membership_id"):
        sponsor = await db.users.find_one(
            {"membership_id": user["sponsor_membership_id"]},
            {"membership_id": 1, "full_name": 1, "mobile": 1},
        )
        if sponsor:
            sponsor.pop("_id", None)

    # Downline (level-1)
    downline = []
    async for u in db.users.find(
        {"sponsor_membership_id": membership_id, "deleted_at": None},
        {"membership_id": 1, "full_name": 1, "mobile": 1, "created_at": 1, "is_active": 1},
    ).sort("created_at", 1):
        u["level"] = 1
        u.pop("_id", None)
        downline.append(u)

    # Payments (all program_purchases)
    payments = []
    async for p in db.program_purchases.find(
        {"user_membership_id": membership_id, "deleted_at": None},
    ).sort("purchase_date", -1):
        prog = await db.programs.find_one(
            {"id": p["program_id"]}, {"name": 1}
        ) or {}
        payments.append(
            {
                "invoice_number": p.get("invoice_number"),
                "purchase_date": p.get("purchase_date"),
                "expiry_date": p.get("expiry_date"),
                "program_id": p.get("program_id"),
                "program_name": prog.get("name") or p.get("program_id"),
                "source": p.get("source") or ("razorpay" if p.get("razorpay_payment_id") else "manual_qr"),
                "taxable_amount": p.get("taxable_amount") or p.get("price_paid"),
                "gst_amount": p.get("gst_amount"),
                "total": p.get("total"),
                "utr": p.get("utr"),
                "razorpay_payment_id": p.get("razorpay_payment_id"),
                "status": p.get("status"),
            }
        )

    # Programs + progress
    programs = []
    async for prog_prog in db.program_progress.find(
        {"user_membership_id": membership_id, "deleted_at": None},
    ):
        prog = await db.programs.find_one(
            {"id": prog_prog["program_id"]}, {"name": 1}
        ) or {}
        cert = await db.certificates.find_one(
            {
                "user_membership_id": membership_id,
                "program_id": prog_prog["program_id"],
                "deleted_at": None,
            },
            {"certificate_number": 1},
        )
        # look up purchase to get validity
        purchase = await db.program_purchases.find_one(
            {
                "user_membership_id": membership_id,
                "program_id": prog_prog["program_id"],
                "deleted_at": None,
            },
            sort=[("purchase_date", -1)],
        ) or {}
        completed_mods = int(prog_prog.get("completed_modules_count") or 0)
        total_mods = int(prog_prog.get("total_modules_count") or 0)
        programs.append(
            {
                "program_id": prog_prog["program_id"],
                "program_name": prog.get("name") or prog_prog["program_id"],
                "purchase_date": purchase.get("purchase_date"),
                "expiry_date": purchase.get("expiry_date"),
                "completed_modules": completed_mods,
                "total_modules": total_mods,
                "percentage": int(round((completed_mods / total_mods * 100) if total_mods else 0)),
                "certificate_number": (cert or {}).get("certificate_number"),
            }
        )

    # Commissions
    commissions = []
    async for c in db.commissions.find(
        {"sponsor_membership_id": membership_id, "deleted_at": None},
    ).sort("created_at", -1):
        c.pop("_id", None)
        commissions.append(c)

    # Activity
    activity = []
    async for a in db.activity_sessions.find(
        {"user_membership_id": membership_id, "deleted_at": None},
    ).sort("completed_at", -1).limit(500):
        a.pop("_id", None)
        activity.append(a)

    # Login history — via audit_log actions containing 'login'
    logins = []
    async for row in db.activity_log.find(
        {
            "$or": [
                {"actor_id": membership_id, "action": {"$regex": "login", "$options": "i"}},
                {"entity_id": membership_id, "action": {"$regex": "login|otp", "$options": "i"}},
            ]
        }
    ).sort("created_at", -1).limit(100):
        row.pop("_id", None)
        logins.append(row)

    # Payouts
    payouts = []
    async for po in db.payouts.find(
        {"user_membership_id": membership_id, "deleted_at": None},
    ).sort("created_at", -1):
        po.pop("_id", None)
        payouts.append(po)

    # Wallet (bank details) & subscription snapshot
    bank = await db.bank_details.find_one(
        {"user_membership_id": membership_id, "deleted_at": None}
    )
    if bank:
        bank.pop("_id", None)

    # Activity meter (cycle status)
    meter = await get_meter(db, membership_id)

    # Aggregates
    total_paid = sum(float(p.get("total") or 0) for p in payments)
    total_commission_earned = sum(
        float(c.get("amount") or 0) for c in commissions if c.get("status") in ("approved", "paid")
    )

    return {
        "generated_at": _now_iso(),
        "profile": user,
        "sponsor": sponsor,
        "meter": meter,
        "bank": bank,
        "aggregates": {
            "total_paid": round(total_paid, 2),
            "total_commission_earned": round(total_commission_earned, 2),
            "downline_count": len(downline),
            "purchases_count": len(payments),
            "programs_touched": len(programs),
        },
        "downline": downline,
        "payments": payments,
        "programs": programs,
        "commissions": commissions,
        "activity": activity,
        "logins": logins,
        "payouts": payouts,
    }


def build_360_excel(payload: dict[str, Any]) -> bytes:
    """Turn a `collect_user_360()` payload into a multi-sheet Excel workbook."""
    u = payload.get("profile") or {}
    sp = payload.get("sponsor") or {}
    ag = payload.get("aggregates") or {}
    meter = payload.get("meter") or {}
    bank = payload.get("bank") or {}

    profile_rows = [
        {"field": "Membership ID", "value": u.get("membership_id", "")},
        {"field": "Full name",     "value": u.get("full_name", "")},
        {"field": "Mobile",        "value": u.get("mobile", "")},
        {"field": "Email",         "value": u.get("email", "") or ""},
        {"field": "State / City",  "value": f"{u.get('state','')} / {u.get('city','')}"},
        {"field": "Address",       "value": u.get("address", "") or ""},
        {"field": "Status",        "value": "active" if u.get("is_active") else (u.get("status") or "inactive")},
        {"field": "Registered on", "value": u.get("created_at", "")},
        {"field": "Sponsor",       "value": f"{sp.get('membership_id','—')} · {sp.get('full_name','—')}" if sp else "—"},
        {"field": "Activity status", "value": meter.get("status", "—")},
        {"field": "Cycle",         "value": f"{meter.get('cycle_start','—')} → {meter.get('cycle_end','—')}"},
        {"field": "Sessions completed", "value": f"{meter.get('completed', 0)} / {meter.get('required', 4)}"},
        {"field": "Total paid",    "value": f"₹{ag.get('total_paid', 0):,.2f}"},
        {"field": "Total commission earned", "value": f"₹{ag.get('total_commission_earned', 0):,.2f}"},
        {"field": "Direct downline", "value": ag.get("downline_count", 0)},
        {"field": "Purchases count", "value": ag.get("purchases_count", 0)},
        {"field": "Bank account", "value": (
            f"{bank.get('account_number','—')} · {bank.get('ifsc','—')} · {bank.get('account_holder_name','—')}"
            if bank else "—"
        )},
    ]

    sheets = [
        ("Profile",     COLUMNS["Profile"],     profile_rows),
        ("Downline",    COLUMNS["Downline"],    payload.get("downline", [])),
        ("Payments",    COLUMNS["Payments"],    payload.get("payments", [])),
        ("Programs",    COLUMNS["Programs"],    payload.get("programs", [])),
        ("Commissions", COLUMNS["Commissions"], payload.get("commissions", [])),
        ("Payouts",     COLUMNS["Payouts"],     payload.get("payouts", [])),
        ("Activity",    COLUMNS["Activity"],    payload.get("activity", [])),
        ("Logins",      COLUMNS["Logins"],      payload.get("logins", [])),
    ]
    return to_excel_multi_sheet(sheets)
