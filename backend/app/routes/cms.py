"""CMS pages — public GET by slug + admin PUT to edit."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin
from app.models.phase7 import CMS_SLUGS, CMSPageUpsert
from app.utils.audit import log_action

router = APIRouter(prefix="/cms", tags=["CMS"])
admin_router = APIRouter(prefix="/admin/cms", tags=["Admin CMS"])


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/pages")
async def list_pages(database: AsyncIOMotorDatabase = Depends(db)):
    """Public listing — only published pages, sorted alphabetically."""
    items = []
    async for row in database.cms_pages.find(
        {"is_published": True, "deleted_at": None}, {"body": 0}
    ).sort("slug", 1):
        row.pop("_id", None)
        items.append(row)
    return {"items": items}


@router.get("/pages/{slug}")
async def get_page(
    slug: str = Path(..., pattern=r"^[a-z0-9-]{2,40}$"),
    database: AsyncIOMotorDatabase = Depends(db),
):
    row = await database.cms_pages.find_one(
        {"slug": slug, "is_published": True, "deleted_at": None}
    )
    if not row:
        # Return an empty stub so the frontend can render a placeholder.
        return {
            "slug": slug,
            "title": CMS_SLUGS.get(slug, slug.title()),
            "body": "",
            "is_published": False,
            "empty": True,
        }
    row.pop("_id", None)
    return row


@admin_router.get("/pages")
async def admin_list_pages(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Admin listing includes unpublished pages + all known slugs."""
    existing: dict[str, dict] = {}
    async for row in database.cms_pages.find({"deleted_at": None}).sort("slug", 1):
        row.pop("_id", None)
        existing[row["slug"]] = row
    items = []
    for slug, default_title in CMS_SLUGS.items():
        row = existing.get(slug) or {
            "slug": slug,
            "title": default_title,
            "body": "",
            "is_published": False,
            "updated_at": None,
        }
        items.append(row)
    # include any custom slugs beyond the reserved set
    for slug, row in existing.items():
        if slug not in CMS_SLUGS:
            items.append(row)
    return {"items": items}


@admin_router.get("/pages/{slug}")
async def admin_get_page(
    slug: str = Path(..., pattern=r"^[a-z0-9-]{2,40}$"),
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    row = await database.cms_pages.find_one({"slug": slug, "deleted_at": None})
    if not row:
        return {
            "slug": slug,
            "title": CMS_SLUGS.get(slug, slug.title()),
            "body": "",
            "is_published": False,
        }
    row.pop("_id", None)
    return row


@admin_router.put("/pages/{slug}")
async def admin_upsert_page(
    slug: str = Path(..., pattern=r"^[a-z0-9-]{2,40}$"),
    body: CMSPageUpsert = None,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    now = _iso()
    doc = body.model_dump()
    existing = await database.cms_pages.find_one({"slug": slug, "deleted_at": None})
    if existing:
        # snapshot previous version
        version = {
            "id": str(uuid.uuid4()),
            "page_slug": slug,
            "title": existing["title"],
            "body": existing["body"],
            "saved_at": existing.get("updated_at", now),
            "created_at": now,
        }
        await database.cms_page_versions.insert_one(version)
        await database.cms_pages.update_one(
            {"_id": existing["_id"]},
            {"$set": {**doc, "updated_at": now, "updated_by": admin["mobile"]}},
        )
    else:
        insert_doc = {
            "id": str(uuid.uuid4()),
            "slug": slug,
            **doc,
            "created_at": now,
            "updated_at": now,
            "updated_by": admin["mobile"],
            "deleted_at": None,
        }
        await database.cms_pages.insert_one(insert_doc)

    await log_action(
        database, actor_id=admin["mobile"], action="cms.page.upsert", entity="cms", entity_id=slug
    )
    row = await database.cms_pages.find_one({"slug": slug, "deleted_at": None})
    if row:
        row.pop("_id", None)
    return row


@admin_router.get("/pages/{slug}/versions")
async def admin_page_versions(
    slug: str = Path(..., pattern=r"^[a-z0-9-]{2,40}$"),
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
    limit: int = 20,
):
    items = []
    async for v in database.cms_page_versions.find({"page_slug": slug}).sort("created_at", -1).limit(limit):
        v.pop("_id", None)
        items.append(v)
    return {"items": items}
