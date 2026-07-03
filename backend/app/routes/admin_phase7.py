"""System + Security settings + Audit-log viewer + File uploads + Banners + Admin Notifications.

Bundled here to keep the route surface tidy. Each block has a clear header.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Path as PathParam, Query, UploadFile
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase7 import (
    BannerUpsert,
    NotificationSend,
    SecuritySettingsUpdate,
    SystemSettingsUpdate,
)
from app.utils.audit import log_action

router = APIRouter(tags=["Admin Phase 7"])


UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_PREFIXES = ("image/", "video/", "audio/", "application/pdf", "application/octet-stream")
MAX_UPLOAD_MB = 200


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get(db_: AsyncIOMotorDatabase, key: str, default=None):
    row = await db_.app_settings.find_one({"key": key, "deleted_at": None})
    return (row or {}).get("value", default)


async def _set(db_: AsyncIOMotorDatabase, key: str, value):
    now = _iso()
    await db_.app_settings.update_one(
        {"key": key},
        {
            "$set": {"value": value, "updated_at": now},
            "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now, "deleted_at": None},
        },
        upsert=True,
    )


# ============ System Settings ============================================


SYSTEM_KEYS = [
    "company_name",
    "company_logo_url",
    "company_address",
    "company_gst_number",
    "support_email",
    "support_mobile",
    "website",
    "social_facebook",
    "social_instagram",
    "social_youtube",
    "social_linkedin",
    "social_twitter",
    "application_version",
    "maintenance_mode",
]


@router.get("/admin/system/settings")
async def get_system_settings(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    out = {}
    for k in SYSTEM_KEYS:
        out[k] = await _get(database, k)
    out.setdefault("company_name", "RIYORA Wellness")
    out.setdefault("application_version", "1.0.0")
    out.setdefault("maintenance_mode", False)
    return out


@router.put("/admin/system/settings")
async def put_system_settings(
    body: SystemSettingsUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    for k, v in body.model_dump(exclude_none=True).items():
        await _set(database, k, v)
    await log_action(database, actor_id=admin["mobile"], action="system.settings.update", entity="settings")
    return await get_system_settings(database, admin)


@router.get("/system/public")
async def get_system_public(database: AsyncIOMotorDatabase = Depends(db)):
    """Non-sensitive settings for public/user pages."""
    out = {}
    for k in [
        "company_name", "company_logo_url", "company_address", "support_email",
        "support_mobile", "website",
        "social_facebook", "social_instagram", "social_youtube",
        "social_linkedin", "social_twitter",
        "application_version", "maintenance_mode",
    ]:
        out[k] = await _get(database, k)
    out.setdefault("company_name", "RIYORA Wellness")
    return out


# ============ Security Settings ==========================================


SECURITY_KEYS = [
    "password_min_length",
    "otp_expiry_seconds",
    "login_attempt_limit",
    "session_timeout_minutes",
]


@router.get("/admin/security/settings")
async def get_security_settings(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    out = {}
    for k in SECURITY_KEYS:
        out[k] = await _get(database, k)
    out.setdefault("password_min_length", 8)
    out.setdefault("otp_expiry_seconds", 300)
    out.setdefault("login_attempt_limit", 5)
    out.setdefault("session_timeout_minutes", 60)
    return out


@router.put("/admin/security/settings")
async def put_security_settings(
    body: SecuritySettingsUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    for k, v in body.model_dump(exclude_none=True).items():
        await _set(database, k, v)
    await log_action(database, actor_id=admin["mobile"], action="security.settings.update", entity="settings")
    return await get_security_settings(database, admin)


# ============ Audit Log Viewer ==========================================


@router.get("/admin/audit-log")
async def audit_log(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    q: str | None = Query(default=None),
    action: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    filters: dict = {}
    if action:
        filters["action"] = {"$regex": action, "$options": "i"}
    if actor:
        filters["actor_membership_id"] = actor
    if q:
        filters["$or"] = [
            {"action": {"$regex": q, "$options": "i"}},
            {"target": {"$regex": q, "$options": "i"}},
            {"actor_membership_id": {"$regex": q, "$options": "i"}},
        ]
    total = await database.activity_log.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for r in database.activity_log.find(filters).sort("created_at", -1).skip(skip).limit(page_size):
        r.pop("_id", None)
        items.append(r)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


# ============ File Uploads ==============================================


@router.post("/admin/uploads", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    if not (file.content_type or "").startswith(ALLOWED_MIME_PREFIXES):
        raise HTTPException(400, f"Unsupported content-type: {file.content_type}")
    # Read + size check
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(413, f"File too large ({size_mb:.1f} MB > {MAX_UPLOAD_MB} MB)")

    file_id = str(uuid.uuid4())
    safe_name = os.path.basename(file.filename or "file")
    ext = ""
    if "." in safe_name:
        ext = "." + safe_name.rsplit(".", 1)[-1].lower()[:8]
    stored_name = f"{file_id}{ext}"
    (UPLOAD_DIR / stored_name).write_bytes(contents)

    doc = {
        "id": file_id,
        "original_name": safe_name,
        "stored_name": stored_name,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "url": f"/api/uploads/{file_id}",
        "uploaded_by": admin["mobile"],
        "created_at": _iso(),
        "updated_at": _iso(),
        "deleted_at": None,
    }
    await database.uploads.insert_one(doc)
    doc.pop("_id", None)
    await log_action(database, actor_id=admin["mobile"], action="upload.create", entity="upload", entity_id=file_id)
    return doc


@router.get("/uploads/{file_id}")
async def get_upload(
    file_id: str = PathParam(...),
    database: AsyncIOMotorDatabase = Depends(db),
):
    """Public endpoint — content itself is not sensitive (URLs are opaque UUIDs)."""
    doc = await database.uploads.find_one({"id": file_id, "deleted_at": None})
    if not doc:
        raise HTTPException(404, "Not found")
    path = UPLOAD_DIR / doc["stored_name"]
    if not path.exists():
        raise HTTPException(404, "File missing on disk")
    return FileResponse(
        str(path),
        media_type=doc.get("content_type") or "application/octet-stream",
        filename=doc.get("original_name") or doc["stored_name"],
    )


@router.get("/admin/uploads")
async def list_uploads(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    filters = {"deleted_at": None}
    total = await database.uploads.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for r in database.uploads.find(filters).sort("created_at", -1).skip(skip).limit(page_size):
        r.pop("_id", None)
        items.append(r)
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size or 1}


@router.delete("/admin/uploads/{file_id}")
async def delete_upload(
    file_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    doc = await database.uploads.find_one({"id": file_id, "deleted_at": None})
    if not doc:
        raise HTTPException(404, "Not found")
    await database.uploads.update_one({"_id": doc["_id"]}, {"$set": {"deleted_at": _iso()}})
    path = UPLOAD_DIR / doc["stored_name"]
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
    await log_action(database, actor_id=admin["mobile"], action="upload.delete", entity="upload", entity_id=file_id)
    return {"success": True}


# ============ Banners ==================================================


@router.get("/banners/active")
async def active_banners(
    placement: str | None = Query(default=None),
    database: AsyncIOMotorDatabase = Depends(db),
):
    now_iso = _iso()
    filters: dict = {
        "deleted_at": None,
        "is_active": True,
        "$and": [
            {"$or": [{"schedule_start": None}, {"schedule_start": {"$lte": now_iso}}]},
            {"$or": [{"schedule_end": None}, {"schedule_end": {"$gte": now_iso}}]},
        ],
    }
    if placement:
        filters["placement"] = placement
    items = []
    async for r in database.banners.find(filters).sort("priority", -1):
        r.pop("_id", None)
        items.append(r)
    return {"items": items}


@router.get("/admin/banners")
async def admin_list_banners(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    items = []
    async for r in database.banners.find({"deleted_at": None}).sort("priority", -1):
        r.pop("_id", None)
        items.append(r)
    return {"items": items}


@router.post("/admin/banners", status_code=201)
async def admin_create_banner(
    body: BannerUpsert,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    doc = {
        "id": str(uuid.uuid4()),
        **body.model_dump(),
        "created_at": _iso(),
        "updated_at": _iso(),
        "created_by": admin["mobile"],
        "deleted_at": None,
    }
    await database.banners.insert_one(doc)
    doc.pop("_id", None)
    await log_action(database, actor_id=admin["mobile"], action="banner.create", entity="banner", entity_id=doc["id"])
    return doc


@router.put("/admin/banners/{banner_id}")
async def admin_update_banner(
    banner_id: str,
    body: BannerUpsert,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    res = await database.banners.update_one(
        {"id": banner_id, "deleted_at": None},
        {"$set": {**body.model_dump(), "updated_at": _iso()}},
    )
    if not res.matched_count:
        raise HTTPException(404, "Banner not found")
    await log_action(database, actor_id=admin["mobile"], action="banner.update", entity="banner", entity_id=banner_id)
    row = await database.banners.find_one({"id": banner_id})
    row.pop("_id", None)
    return row


@router.delete("/admin/banners/{banner_id}")
async def admin_delete_banner(
    banner_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    res = await database.banners.update_one(
        {"id": banner_id, "deleted_at": None}, {"$set": {"deleted_at": _iso()}}
    )
    if not res.matched_count:
        raise HTTPException(404, "Banner not found")
    await log_action(database, actor_id=admin["mobile"], action="banner.delete", entity="banner", entity_id=banner_id)
    return {"success": True}


# ============ Admin Notifications ======================================


@router.post("/admin/notifications", status_code=201)
async def admin_send_notification(
    body: NotificationSend,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    now = _iso()
    template_id = str(uuid.uuid4())
    # Save the template row (so admin can see history).
    template = {
        "id": template_id,
        "title": body.title,
        "body": body.body,
        "category": body.category,
        "is_broadcast": body.is_broadcast,
        "target_membership_ids": body.target_membership_ids,
        "cta_link": body.cta_link,
        "sent_by": admin["mobile"],
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "delivered_count": 0,
    }
    await database.notification_templates.insert_one(template)

    # Materialise per-user rows.
    if body.is_broadcast:
        user_ids: list[str] = []
        async for u in database.users.find(
            {"deleted_at": None, "is_active": True}, {"membership_id": 1}
        ):
            user_ids.append(u["membership_id"])
    else:
        user_ids = body.target_membership_ids or []

    docs = []
    for mid in user_ids:
        docs.append(
            {
                "id": str(uuid.uuid4()),
                "user_membership_id": mid,
                "title": body.title,
                "body": body.body,
                "category": body.category,
                "is_broadcast": body.is_broadcast,
                "template_id": template_id,
                "cta_link": body.cta_link,
                "is_read": False,
                "meta": {"template_id": template_id},
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
        )
    if docs:
        await database.notifications.insert_many(docs)
    await database.notification_templates.update_one(
        {"id": template_id}, {"$set": {"delivered_count": len(docs), "updated_at": _iso()}}
    )
    await log_action(
        database,
        actor_id=admin["mobile"],
        action="notification.send",
        entity="notification",
        entity_id=template_id,
        meta={"delivered": len(docs), "broadcast": body.is_broadcast},
    )
    return {"template_id": template_id, "delivered_count": len(docs)}


@router.get("/admin/notifications")
async def admin_list_notifications(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    filters = {"deleted_at": None}
    total = await database.notification_templates.count_documents(filters)
    skip = (page - 1) * page_size
    items = []
    async for r in database.notification_templates.find(filters).sort("created_at", -1).skip(skip).limit(page_size):
        r.pop("_id", None)
        items.append(r)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size or 1,
    }


# ============ User Notifications (read-side) ============================


@router.get("/notifications/me")
async def my_notifications(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    unread_only: bool = False,
    limit: int = 50,
):
    filters = {"user_membership_id": current["membership_id"], "deleted_at": None}
    if unread_only:
        filters["is_read"] = False
    items = []
    async for n in database.notifications.find(filters).sort("created_at", -1).limit(min(limit, 200)):
        n.pop("_id", None)
        items.append(n)
    unread = await database.notifications.count_documents(
        {"user_membership_id": current["membership_id"], "is_read": False, "deleted_at": None}
    )
    return {"items": items, "unread": unread}


@router.post("/notifications/me/read-all")
async def mark_all_read(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    res = await database.notifications.update_many(
        {"user_membership_id": current["membership_id"], "is_read": False, "deleted_at": None},
        {"$set": {"is_read": True, "updated_at": _iso()}},
    )
    return {"success": True, "updated": res.modified_count}
