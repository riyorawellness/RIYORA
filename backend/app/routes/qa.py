"""QA / Business Rule Validation route."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin
from app.services.brv import build_pdf, run_brv
from app.utils.audit import log_action

router = APIRouter(prefix="/admin/qa", tags=["Admin QA"])


@router.get("/brv")
async def brv_json(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Return the Business Rule Validation Report as JSON."""
    return await run_brv(database)


@router.get("/brv/pdf")
async def brv_pdf(
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    """Return the Business Rule Validation Report as a downloadable PDF."""
    report = await run_brv(database)
    pdf_bytes = build_pdf(report)
    await log_action(
        database, actor_id=admin["mobile"], action="qa.brv.pdf",
        entity="qa", meta={"passed": report["passed"], "failed": report["failed"]},
    )
    filename = f"riyora-brv-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
