"""PDF Reports service — generates 5 user-facing reports on demand.

Reports:
  * referral      — all downline members with sub/purchase status
  * income        — commission ledger with status buckets
  * downline      — pure member tree (name/id/level/joining/status)
  * subscription  — Inner Peace cycles + activity per cycle
  * transaction   — all payments (program_purchases) with GST + status

All reports use the same header + branding.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.commission_engine import summarise_user

ROYAL = colors.HexColor("#0B1A5B")
GOLD = colors.HexColor("#B08A3E")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("H1", parent=s["Heading1"], fontSize=22, leading=26, textColor=ROYAL))
    s.add(
        ParagraphStyle(
            "Eyebrow", parent=s["Normal"], fontSize=8, leading=10, textColor=GOLD,
            fontName="Helvetica-Bold",
        )
    )
    s.add(ParagraphStyle("Muted", parent=s["Normal"], fontSize=9, textColor=MUTED))
    s.add(ParagraphStyle("Body", parent=s["Normal"], fontSize=9, textColor=INK))
    return s


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d %b %Y")
    except Exception:
        return iso


def _fmt_amt(v: Any) -> str:
    try:
        return f"Rs. {float(v or 0):,.2f}"
    except Exception:
        return "Rs. 0.00"


def _header(styles, user: dict, title: str) -> list:
    flow = [
        Paragraph("R I Y O R A &nbsp; W E L L N E S S", styles["Eyebrow"]),
        Paragraph(title, styles["H1"]),
        Paragraph(
            f"Member: <b>{user.get('full_name','—')}</b> · Membership ID "
            f"<b>{user.get('membership_id','—')}</b> · Generated "
            f"{datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}",
            styles["Muted"],
        ),
        Spacer(1, 10),
    ]
    return flow


def _table(rows: list[list[Any]], col_widths: list[float]) -> Table:
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ROYAL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tbl


async def _build(doc_body: list, title: str, user: dict, styles) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=title,
    )
    flow = _header(styles, user, title) + doc_body
    doc.build(flow)
    b = buf.getvalue()
    buf.close()
    return b


async def generate_report(
    db: AsyncIOMotorDatabase, user: dict, report_type: str
) -> tuple[bytes, str]:
    """Return (pdf_bytes, filename)."""
    styles = _styles()
    membership_id = user["membership_id"]

    if report_type == "income":
        summary = await summarise_user(db, membership_id)
        summary_rows = [
            ["Bucket", "Amount", "Count"],
            ["Pending",  _fmt_amt(summary["pending"]),  summary["counts"]["pending"]],
            ["Approved (payable)", _fmt_amt(summary["approved"]), summary["counts"]["approved"]],
            ["Paid",     _fmt_amt(summary["paid"]),     summary["counts"]["paid"]],
            ["Rejected", _fmt_amt(summary["rejected"]), summary["counts"]["rejected"]],
            ["Lifetime", _fmt_amt(summary["lifetime"]), ""],
        ]
        rows = [["Date", "Program", "Buyer", "Level", "Amount", "Status"]]
        async for c in db.commissions.find(
            {"sponsor_membership_id": membership_id, "deleted_at": None}
        ).sort("created_at", -1).limit(500):
            rows.append([
                _fmt_date(c.get("created_at")),
                (c.get("program_name") or "—")[:30],
                f"{c.get('buyer_name','—')}\n{c.get('buyer_membership_id','')}",
                f"L{c.get('level')}",
                _fmt_amt(c.get("amount")),
                (c.get("status") or "").capitalize(),
            ])
        body = [
            Paragraph("<b>Summary</b>", styles["Body"]),
            _table(summary_rows, [40 * mm, 45 * mm, 25 * mm]),
            Spacer(1, 12),
            Paragraph("<b>Recent commissions</b>", styles["Body"]),
            Spacer(1, 4),
            _table(rows, [22 * mm, 40 * mm, 45 * mm, 14 * mm, 25 * mm, 25 * mm]),
        ]
        return await _build(body, "Income Report", user, styles), f"income-{membership_id}.pdf"

    if report_type in {"referral", "downline"}:
        rows = [["Membership ID", "Name", "Level", "Joined", "Status"]]
        # Walk 3 levels downline
        current_level = [membership_id]
        depth = 0
        total = 0
        while current_level and depth < 3:
            async for d in db.referral_tree.find(
                {"sponsor_membership_id": {"$in": current_level}, "deleted_at": None}
            ):
                d.pop("_id", None)
                m = await db.memberships.find_one({"membership_id": d["user_membership_id"]}, {"owner_name": 1})
                rows.append([
                    d["user_membership_id"],
                    (m or {}).get("owner_name") or "—",
                    f"L{depth + 1}",
                    _fmt_date(d.get("joining_date")),
                    (d.get("status") or "active").capitalize(),
                ])
                total += 1
            next_ids = []
            async for d in db.referral_tree.find(
                {"sponsor_membership_id": {"$in": current_level}, "deleted_at": None},
                {"user_membership_id": 1},
            ):
                next_ids.append(d["user_membership_id"])
            current_level = next_ids
            depth += 1

        title = "Referral Report" if report_type == "referral" else "Downline Report"
        body = [
            Paragraph(f"<b>Total downline members:</b> {total}", styles["Body"]),
            Spacer(1, 6),
            _table(rows, [30 * mm, 55 * mm, 15 * mm, 30 * mm, 20 * mm]),
        ]
        return await _build(body, title, user, styles), f"{report_type}-{membership_id}.pdf"

    if report_type == "subscription":
        rows = [["Cycle Start", "Cycle End", "Status", "Sessions", "Payment", "Total"]]
        async for p in db.program_purchases.find(
            {
                "user_membership_id": membership_id,
                "deleted_at": None,
                "$or": [{"subscription_id": {"$ne": None}}, {"source": "subscription_mock"}],
            }
        ).sort("purchase_date", -1):
            p.pop("_id", None)
            sessions = await db.activity_sessions.count_documents(
                {"subscription_purchase_id": p["id"], "deleted_at": None}
            )
            rows.append([
                _fmt_date(p.get("purchase_date")),
                _fmt_date(p.get("expiry_date")),
                (p.get("status") or "").capitalize(),
                str(sessions),
                p.get("payment_status", "captured"),
                _fmt_amt(p.get("total")),
            ])
        if len(rows) == 1:
            rows.append(["—", "—", "—", "—", "—", "—"])
        body = [
            _table(rows, [22 * mm, 22 * mm, 20 * mm, 20 * mm, 25 * mm, 25 * mm]),
        ]
        return await _build(body, "Subscription Report", user, styles), f"subscription-{membership_id}.pdf"

    if report_type == "transaction":
        rows = [["Date", "Invoice", "Program", "Amount", "GST", "Total", "Status"]]
        async for p in db.program_purchases.find(
            {"user_membership_id": membership_id, "deleted_at": None}
        ).sort("purchase_date", -1):
            p.pop("_id", None)
            prog = await db.programs.find_one({"id": p["program_id"], "deleted_at": None}, {"name": 1})
            rows.append([
                _fmt_date(p.get("purchase_date")),
                p.get("invoice_number", "—"),
                ((prog or {}).get("name") or "—")[:26],
                _fmt_amt(p.get("taxable_amount") or p.get("price_paid")),
                _fmt_amt(p.get("gst_amount")),
                _fmt_amt(p.get("total")),
                (p.get("status") or "").capitalize(),
            ])
        if len(rows) == 1:
            rows.append(["—", "—", "—", "—", "—", "—", "—"])
        body = [
            _table(rows, [22 * mm, 30 * mm, 40 * mm, 20 * mm, 20 * mm, 22 * mm, 20 * mm]),
        ]
        return await _build(body, "Transaction Report", user, styles), f"transactions-{membership_id}.pdf"

    raise ValueError(f"Unknown report type: {report_type}")
