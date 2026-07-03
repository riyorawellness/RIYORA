"""User PDF report exports."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_user
from app.services.reports import generate_report

router = APIRouter(prefix="/reports", tags=["Reports"])


ALLOWED = {"referral", "income", "downline", "subscription", "transaction"}


@router.get("/{report_type}")
async def download_report(
    report_type: str = Path(...),
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    if report_type not in ALLOWED:
        raise HTTPException(400, f"Unknown report type. Allowed: {sorted(ALLOWED)}")
    pdf_bytes, filename = await generate_report(database, current, report_type)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
