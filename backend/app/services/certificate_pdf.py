"""Elegant one-page landscape-A4 PDF certificate generator.

Given a `certificates` document (from the DB) + the user's full_name +
membership_id, returns PDF bytes suitable for `application/pdf` streaming.

Uses only ReportLab primitives (no HTML→PDF pipeline), so no extra system
deps are needed on the VPS.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


# Brand palette (matches web app CSS vars)
ROYAL      = colors.HexColor("#0B1A5B")
ROYAL_DEEP = colors.HexColor("#050D3E")
GOLD       = colors.HexColor("#B08A3E")
CREAM      = colors.HexColor("#F7F1E1")
INK        = colors.HexColor("#1F2937")
MUTED      = colors.HexColor("#6B7280")
BORDER     = colors.HexColor("#E5E7EB")


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        # Accept both bare-date and full ISO strings.
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %B %Y")
    except Exception:  # noqa: BLE001
        return iso.split("T", 1)[0] if isinstance(iso, str) else str(iso)


def render_certificate_pdf(
    cert: dict[str, Any],
    user_full_name: str,
    membership_id: str,
) -> bytes:
    """Return bytes of a single-page landscape-A4 certificate PDF."""
    buf = io.BytesIO()
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    # ---------- outer decorative border ----------
    margin = 12 * mm
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.rect(margin, margin, page_w - 2 * margin, page_h - 2 * margin, stroke=1, fill=0)
    inner = margin + 4 * mm
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.6)
    c.rect(inner, inner, page_w - 2 * inner, page_h - 2 * inner, stroke=1, fill=0)

    # ---------- header brand strip ----------
    strip_h = 22 * mm
    c.setFillColor(ROYAL_DEEP)
    c.rect(inner, page_h - inner - strip_h, page_w - 2 * inner, strip_h, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(inner + 8 * mm, page_h - inner - 8 * mm, "RIYORA")
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 9)
    c.drawString(inner + 22 * mm, page_h - inner - 8 * mm, "WELLNESS")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.6))
    c.drawRightString(
        page_w - inner - 8 * mm, page_h - inner - 8 * mm,
        "Certificate of Completion",
    )
    c.setFillColor(colors.Color(1, 1, 1, alpha=0.5))
    c.setFont("Helvetica", 7)
    c.drawRightString(
        page_w - inner - 8 * mm, page_h - inner - 14 * mm,
        f"Verify · {cert.get('verification_number', '')}",
    )

    # ---------- body ----------
    center_x = page_w / 2

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(center_x, page_h - inner - 40 * mm, "CERTIFICATE OF COMPLETION")

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 12)
    c.drawCentredString(center_x, page_h - inner - 55 * mm, "This certificate is proudly awarded to")

    # Name
    c.setFillColor(ROYAL_DEEP)
    c.setFont("Helvetica-Bold", 34)
    name = (user_full_name or cert.get("user_name") or "").strip() or "—"
    c.drawCentredString(center_x, page_h - inner - 78 * mm, name)

    # underline swash
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    line_w = 100 * mm
    c.line(
        center_x - line_w / 2, page_h - inner - 84 * mm,
        center_x + line_w / 2, page_h - inner - 84 * mm,
    )

    # Body copy
    c.setFillColor(INK)
    c.setFont("Helvetica", 12)
    c.drawCentredString(
        center_x, page_h - inner - 96 * mm,
        "for successfully completing every module of the program",
    )

    # Program
    c.setFillColor(ROYAL)
    c.setFont("Helvetica-Bold", 22)
    program_name = cert.get("program_name") or "—"
    c.drawCentredString(center_x, page_h - inner - 112 * mm, program_name)

    # Completion date
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 11)
    completed_on = _fmt_date(cert.get("completion_date") or cert.get("issue_date"))
    c.drawCentredString(
        center_x, page_h - inner - 124 * mm,
        f"Completed on {completed_on}",
    )

    # ---------- footer info row ----------
    footer_y = inner + 18 * mm
    # divider
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(inner + 8 * mm, footer_y + 12 * mm, page_w - inner - 8 * mm, footer_y + 12 * mm)

    def _cell(x_center: float, label: str, value: str) -> None:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        c.drawCentredString(x_center, footer_y + 6 * mm, label.upper())
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x_center, footer_y, value or "—")

    _cell(page_w * 0.25, "Membership ID",       membership_id or "—")
    _cell(page_w * 0.50, "Certificate No.",     cert.get("certificate_number", ""))
    _cell(page_w * 0.75, "Issued On",           _fmt_date(cert.get("issue_date")))

    # ---------- watermark (extremely subtle) ----------
    c.saveState()
    c.setFillColor(colors.Color(0.05, 0.10, 0.36, alpha=0.04))
    c.setFont("Helvetica-Bold", 90)
    c.translate(page_w / 2, page_h / 2)
    c.rotate(30)
    c.drawCentredString(0, 0, "RIYORA")
    c.restoreState()

    c.showPage()
    c.save()
    return buf.getvalue()
