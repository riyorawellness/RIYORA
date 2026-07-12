"""Admin backup + restore endpoints.

- GET  /admin/backups                 → list all archived backups
- POST /admin/backups/create          → run a fresh mongodump (password gate)
- POST /admin/backups/{name}/restore  → mongorestore --drop (password gate)
- DELETE /admin/backups/{name}        → delete backup file (password gate)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.deps import db, get_current_admin
from app.core.security import verify_password
from app.services import backup as backup_svc
from app.utils.audit import log_action

router = APIRouter(prefix="/admin/backups", tags=["Admin Backups"])


class PasswordBody(BaseModel):
    admin_password: str = Field(..., min_length=1)
    reason: str | None = Field(default=None, max_length=64)


async def _require_password(
    admin: dict, admin_password: str, database: AsyncIOMotorDatabase
) -> None:
    fresh = await database.admins.find_one(
        {"mobile": admin["mobile"], "deleted_at": None}
    )
    if not fresh or not verify_password(admin_password, fresh.get("password_hash", "")):
        raise HTTPException(status_code=403, detail="Admin password is incorrect")


@router.get("")
async def list_backups(
    admin: dict = Depends(get_current_admin),
):
    return {"items": backup_svc.list_backups()}


@router.post("/create")
async def create_backup(
    body: PasswordBody,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    await _require_password(admin, body.admin_password, database)
    try:
        meta = await backup_svc.create_backup(reason=body.reason or "manual")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Backup failed: {e}")
    await log_action(
        database,
        actor_id=admin["mobile"],
        action="backup.create",
        entity="backup",
        entity_id=meta["filename"],
        meta=meta,
    )
    return {"success": True, "backup": meta}


@router.post("/{filename}/restore")
async def restore_backup(
    filename: str,
    body: PasswordBody,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    await _require_password(admin, body.admin_password, database)
    try:
        result = await backup_svc.restore_backup(filename, drop=True)
    except FileNotFoundError:
        raise HTTPException(404, "Backup not found")
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Restore failed: {e}")
    await log_action(
        database,
        actor_id=admin["mobile"],
        action="backup.restore",
        entity="backup",
        entity_id=filename,
        meta=result,
    )
    return {"success": True, "restored": result}


@router.delete("/{filename}")
async def delete_backup(
    filename: str,
    body: PasswordBody,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    await _require_password(admin, body.admin_password, database)
    try:
        ok = backup_svc.delete_backup(filename)
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    if not ok:
        raise HTTPException(404, "Backup not found")
    await log_action(
        database,
        actor_id=admin["mobile"],
        action="backup.delete",
        entity="backup",
        entity_id=filename,
    )
    return {"success": True}
