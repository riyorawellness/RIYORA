"""Simple GST-compliant PDF invoice generator using ReportLab.

Given a purchase document (from `program_purchases` collection), returns bytes
containing a clean, single-page A4 PDF. Also persists a copy to
`/app/backend/invoices/{invoice_number}.pdf` for direct downloads.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INVOICE_DIR = Path(__file__).resolve().parent.parent.parent / "invoices"
INVOICE_DIR.mkdir(parents=True, exist_ok=True)


ROYAL = colors.HexColor("#0B1A5B")
GOLD = colors.HexColor("#B08A3E")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")


def _styles():
    s = getSampleStyleSheet()
    s.add(
        ParagraphStyle(
            name="H1", parent=s["Heading1"], fontSize=22, leading=26,
            textColor=ROYAL, spaceAfter=2,
        )
    )
    s.add(
        ParagraphStyle(
            name="Eyebrow", parent=s["Normal"], fontSize=8, leading=10,
            textColor=GOLD, spaceAfter=0, alignment=0,
            fontName="Helvetica-Bold",
        )
    )
    s.add(ParagraphStyle(name="Muted", parent=s["Normal"], fontSize=9, textColor=MUTED))
    s.add(ParagraphStyle(name="Body", parent=s["Normal"], fontSize=10, textColor=INK))
    s.add(ParagraphStyle(name="RightBold", parent=s["Normal"], fontSize=10,
                         textColor=INK, alignment=2, fontName="Helvetica-Bold"))
    return s


def _fmt_inr(v: float) -> str:
    v = float(v or 0)
    return f"Rs. {v:,.2f}"


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y")
    except Exception:
        return iso


def generate_invoice_pdf(
    *,
    purchase: dict,
    program: dict,
    user: dict,
    company_gst_number: str | None = None,
    company_name: str = "RIYORA Wellness",
    company_address: str = "care@riyorawellness.com  |  +91-9999999999",
) -> tuple[bytes, str]:
    """Render a clean invoice. Returns (pdf_bytes, saved_path).

    Persists to `/app/backend/invoices/<invoice_number>.pdf`.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {purchase.get('invoice_number','')}",
    )
    s = _styles()

    flow: list = []

    # Header
    flow.append(Paragraph("R I Y O R A &nbsp; W E L L N E S S", s["Eyebrow"]))
    flow.append(Paragraph("Tax Invoice", s["H1"]))
    flow.append(Paragraph("Heal. Learn. Earn.", s["Muted"]))
    flow.append(Spacer(1, 6))

    # Company / Customer table
    company_lines = [
        f"<b>{company_name}</b>",
        company_address,
    ]
    if company_gst_number:
        company_lines.append(f"GSTIN: {company_gst_number}")

    customer_lines = [
        f"<b>{user.get('full_name','—')}</b>",
        f"Membership: {user.get('membership_id','—')}",
        f"Mobile: +91 {user.get('mobile','—')}",
    ]
    header_tbl = Table(
        [
            [
                Paragraph("<br/>".join(company_lines), s["Body"]),
                Paragraph("<br/>".join(customer_lines), s["Body"]),
            ],
            [
                Paragraph(
                    f"<b>Invoice #</b>  {purchase.get('invoice_number','—')}<br/>"
                    f"<b>Date</b>  {_fmt_date(purchase.get('purchase_date'))}",
                    s["Body"],
                ),
                Paragraph(
                    f"<b>Payment</b>  {purchase.get('payment_status','captured')}<br/>"
                    f"<b>Order Id</b>  {purchase.get('razorpay_order_id','—')}",
                    s["Body"],
                ),
            ],
        ],
        colWidths=[85 * mm, 85 * mm],
    )
    header_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#E5E7EB")),
            ]
        )
    )
    flow.append(header_tbl)
    flow.append(Spacer(1, 10))

    # Line items
    price_paid = float(purchase.get("price_paid") or 0)
    discount = float(purchase.get("discount") or 0)
    taxable = float(purchase.get("taxable_amount") or (price_paid - discount))
    gst_pct = float(purchase.get("gst_percent") or program.get("gst_percent") or 18)
    gst_amount = float(purchase.get("gst_amount") or 0)
    total = float(purchase.get("total") or (taxable + gst_amount))

    lines_data = [
        ["#", "Description", "Rate", "Discount", "Amount"],
        [
            "1",
            f"{program.get('name','Program')}\n"
            f"Validity {program.get('validity_days','—')} days",
            _fmt_inr(price_paid),
            _fmt_inr(discount),
            _fmt_inr(taxable),
        ],
    ]
    tbl = Table(lines_data, colWidths=[10 * mm, 90 * mm, 25 * mm, 22 * mm, 23 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ROYAL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    flow.append(tbl)
    flow.append(Spacer(1, 6))

    # Totals block
    totals = Table(
        [
            ["Sub-total", _fmt_inr(taxable)],
            [f"GST @ {gst_pct:g}%", _fmt_inr(gst_amount)],
            ["Grand Total", _fmt_inr(total)],
        ],
        colWidths=[45 * mm, 35 * mm],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEABOVE", (0, 2), (-1, 2), 0.8, ROYAL),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 2), (-1, 2), ROYAL),
            ]
        )
    )
    flow.append(totals)
    flow.append(Spacer(1, 16))

    # Footer
    flow.append(
        Paragraph(
            "This is a computer-generated invoice. Purchase is non-refundable except "
            "as per RIYORA Wellness refund policy. All disputes subject to applicable jurisdiction.",
            s["Muted"],
        )
    )

    doc.build(flow)
    pdf_bytes = buf.getvalue()
    buf.close()

    out_path = INVOICE_DIR / f"{purchase.get('invoice_number','invoice')}.pdf"
    try:
        out_path.write_bytes(pdf_bytes)
    except OSError:
        pass
    return pdf_bytes, str(out_path)


__all__ = ["generate_invoice_pdf", "INVOICE_DIR"]
