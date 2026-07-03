"""Secure content streaming — signed JWT-guarded video/audio/PDF URLs.

Flow:
  1. UI calls POST /api/content/token with (program_id, module_id, resource)
     — backend validates purchase + validity + module unlock, then returns
       a short-lived JWT + streaming URL /content/stream/{token}.
  2. Player hits GET /content/stream/{token} — the endpoint decodes,
     re-verifies user identity, and redirects (302) to the underlying
     admin-configured URL (video/audio/pdf). No download button, no
     right-click download UI is served here.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_user
from app.services.program_engine import is_module_unlocked
from app.services.validity import get_active_purchase
from app.utils.file_token import decode_content_token, issue_content_token

router = APIRouter(prefix="/content", tags=["Secure Content"])

_RESOURCE_TO_FIELD = {"video": "video_url", "audio": "audio_url", "pdf": "pdf_url"}


@router.post("/token")
async def issue_token(
    program_id: str = Query(...),
    module_id: str = Query(...),
    resource: str = Query(..., pattern="^(video|audio|pdf)$"),
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    # 1. Verify active purchase.
    active = await get_active_purchase(database, current["membership_id"], program_id)
    if not active:
        raise HTTPException(403, "No active purchase for this program or validity expired")

    # 2. Verify module exists in program.
    module = await database.program_modules.find_one(
        {"id": module_id, "program_id": program_id, "deleted_at": None}
    )
    if not module:
        raise HTTPException(404, "Module not found")

    # 3. Enforce sequential unlock.
    if not await is_module_unlocked(database, current["membership_id"], program_id, module):
        raise HTTPException(403, "Complete the previous module to unlock this one")

    # 4. Resolve the resource URL from the module.
    field = _RESOURCE_TO_FIELD[resource]
    resource_url = module.get(field)
    if not resource_url:
        raise HTTPException(404, f"This module has no {resource} content")

    token, ttl = issue_content_token(
        user_membership_id=current["membership_id"],
        program_id=program_id,
        module_id=module_id,
        resource=resource,
        resource_url=resource_url,
    )
    return {
        "stream_url": f"/api/content/stream/{token}",
        "expires_in_seconds": ttl,
        "resource": resource,
        # Watermark payload for UI overlay.
        "watermark": {
            "user_name": current.get("full_name"),
            "membership_id": current["membership_id"],
        },
    }


@router.get("/stream/{token}")
async def stream(token: str, database: AsyncIOMotorDatabase = Depends(db)):
    try:
        payload = decode_content_token(token)
    except Exception as e:
        raise HTTPException(401, "Invalid or expired content token") from e

    # Re-verify the user still has access (edge case: purchase expired between
    # token issue and stream request).
    active = await get_active_purchase(database, payload["sub"], payload["pid"])
    if not active:
        raise HTTPException(403, "Access revoked")

    # 302 redirect to the underlying URL. Storage-layer signed URL would go here
    # once Emergent Object Storage is wired.
    resp = RedirectResponse(url=payload["url"], status_code=302)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Disposition"] = "inline"  # Never trigger download.
    return resp
