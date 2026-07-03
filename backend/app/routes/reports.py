"""User report exports — PDF (legacy), CSV, Excel."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_user
from app.services.exports import export_table
from app.services.user_reports import build_user_report

router = APIRouter(prefix="/reports", tags=["Reports"])


ALLOWED = {"referral", "income", "downline", "subscription", "transaction"}

TITLE_MAP = {
    "referral": "Referral Report",
    "income": "Income Report",
    "downline": "Downline Report",
    "subscription": "Subscription Report",
    "transaction": "Transaction Report",
}


@router.get("/{report_type}")
async def download_report(
    report_type: str = Path(...),
    fmt: str = Query(default="pdf", pattern=r"^(pdf|csv|excel)$"),
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    if report_type not in ALLOWED:
        raise HTTPException(400, f"Unknown report type. Allowed: {sorted(ALLOWED)}")
    columns, rows, summary_lines = await build_user_report(database, current, report_type)

    subtitle = (
        f"Member: {current.get('full_name','—')} · "
        f"Membership ID {current.get('membership_id','—')}"
    )
    content, media_type, filename = export_table(
        fmt,
        columns=columns,
        rows=rows,
        title=TITLE_MAP[report_type],
        filename_stem=f"riyora-{report_type}-{current.get('membership_id','me')}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        subtitle=subtitle,
        summary_lines=summary_lines,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
