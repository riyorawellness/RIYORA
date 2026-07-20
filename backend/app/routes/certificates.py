"""Certificates — user list/get/download, admin CRUD (issue/revoke)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import CertificateCreate, CertificateUpdate, PaginatedResponse
from app.repositories.base import BaseRepository
from app.services.certificate_pdf import render_certificate_pdf

router = APIRouter(prefix="/certificates", tags=["Certificates"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(database, "certificates", ["certificate_number"], "-issue_date,-created_at")


@router.get("/me", response_model=PaginatedResponse)
async def list_my_certificates(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    program_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str = Query(default="-issue_date"),
):
    filters = {"user_membership_id": current["membership_id"], "status": "issued"}
    if program_id:
        filters["program_id"] = program_id
    return await _repo(database).list_paginated(filters, None, sort, page, page_size)


@router.get("/me/{certificate_id}")
async def get_my_certificate(
    certificate_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    doc = await _repo(database).get_by(
        {"id": certificate_id, "user_membership_id": current["membership_id"]}
    )
    if not doc:
        raise HTTPException(404, "Certificate not found")
    return doc


@router.get("/me/{certificate_id}/pdf")
async def download_my_certificate_pdf(
    certificate_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    """Generate a landscape-A4 PDF of the certificate on demand and stream it
    as `application/pdf`. Filename hint uses the certificate_number so
    the file lands nicely in the user's Downloads folder.
    """
    cert = await _repo(database).get_by(
        {"id": certificate_id, "user_membership_id": current["membership_id"]}
    )
    if not cert:
        raise HTTPException(404, "Certificate not found")
    user = await database.users.find_one(
        {"membership_id": current["membership_id"], "deleted_at": None}
    ) or {}
    full_name = (cert.get("user_name") or user.get("full_name") or "").strip()
    pdf_bytes = render_certificate_pdf(
        cert=cert,
        user_full_name=full_name,
        membership_id=current["membership_id"],
    )
    safe_num = (cert.get("certificate_number") or certificate_id).replace("/", "_")
    filename = f"RIYORA-Certificate-{safe_num}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=60",
        },
    )


# ------------------------- Admin ------------------------------------------
@router.get("/admin", response_model=PaginatedResponse)
async def admin_list_certificates(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    user_membership_id: str | None = Query(default=None),
    program_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str = Query(default="-issue_date"),
):
    filters = {}
    if user_membership_id:
        filters["user_membership_id"] = user_membership_id
    if program_id:
        filters["program_id"] = program_id
    if status:
        filters["status"] = status
    return await _repo(database).list_paginated(filters, search, sort, page, page_size)


@router.post("/admin", status_code=201)
async def admin_issue_certificate(
    body: CertificateCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    if not await database.users.find_one({"membership_id": body.user_membership_id, "deleted_at": None}):
        raise HTTPException(400, "user_membership_id does not exist")
    if not await database.programs.find_one({"id": body.program_id, "deleted_at": None}):
        raise HTTPException(400, "program_id does not exist")
    if await database.certificates.find_one({"certificate_number": body.certificate_number, "deleted_at": None}):
        raise HTTPException(409, "certificate_number already exists")
    return await _repo(database).create(body.model_dump(), actor=admin["mobile"])


@router.put("/admin/{certificate_id}")
async def admin_update_certificate(
    certificate_id: str,
    body: CertificateUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updated = await _repo(database).update(certificate_id, body.model_dump(exclude_none=True), actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Certificate not found")
    return updated


@router.delete("/admin/{certificate_id}")
async def admin_delete_certificate(
    certificate_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    ok = await _repo(database).soft_delete(certificate_id, actor=admin["mobile"])
    if not ok:
        raise HTTPException(404, "Certificate not found")
    return {"message": "Certificate revoked"}
