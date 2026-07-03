"""Refer & Earn — dashboard, tree, team, share (QR)."""
from __future__ import annotations

import base64
import io
from typing import Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase6 import ReferralSettingsUpdate
from app.services.activity_meter import get_meter
from app.services.commission_engine import summarise_user

router = APIRouter(prefix="/referrals", tags=["Refer & Earn"])
settings = get_settings()


def _referral_link(app_url: str, membership_id: str) -> str:
    base = (app_url or "").rstrip("/")
    return f"{base}/join/{membership_id}"


@router.get("/dashboard")
async def dashboard(
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    app_url: Optional[str] = Query(default=None),
):
    membership_id = current["membership_id"]
    earnings = await summarise_user(database, membership_id)
    meter = await get_meter(database, membership_id)
    # Downline counts by level.
    count_by_level: dict[str, int] = {"L1": 0, "L2": 0, "L3": 0}
    current_level = [membership_id]
    for depth in (1, 2, 3):
        next_ids = []
        async for d in database.referral_tree.find(
            {"sponsor_membership_id": {"$in": current_level}, "deleted_at": None},
            {"user_membership_id": 1},
        ):
            count_by_level[f"L{depth}"] += 1
            next_ids.append(d["user_membership_id"])
        current_level = next_ids

    link = _referral_link(app_url or "", membership_id)
    return {
        "membership_id": membership_id,
        "referral_id": membership_id,
        "referral_link": link,
        "sponsor_name": current.get("sponsor_name"),
        "sponsor_membership_id": current.get("sponsor_membership_id"),
        "earnings": earnings,
        "activity": meter,
        "team_counts": count_by_level,
        "total_downline": sum(count_by_level.values()),
    }


@router.get("/share/qr")
async def share_qr(
    current: dict = Depends(get_current_user),
    app_url: Optional[str] = Query(default=None),
    format: str = Query(default="dataurl", pattern="^(dataurl|json)$"),
):
    link = _referral_link(app_url or "", current["membership_id"])
    img = qrcode.make(link)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    if format == "dataurl":
        return {"data_url": f"data:image/png;base64,{b64}", "link": link}
    return {"png_base64": b64, "link": link}


@router.get("/team")
async def team(
    level: int = Query(default=1, ge=1, le=3),
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    membership_id = current["membership_id"]
    # Walk BFS to the requested level.
    current_ids = [membership_id]
    for _ in range(level):
        next_ids = []
        async for d in database.referral_tree.find(
            {"sponsor_membership_id": {"$in": current_ids}, "deleted_at": None},
            {"user_membership_id": 1},
        ):
            next_ids.append(d["user_membership_id"])
        current_ids = next_ids

    if not current_ids:
        return {"items": [], "level": level, "count": 0}

    # Fetch full node info.
    items = []
    async for node in database.referral_tree.find(
        {"user_membership_id": {"$in": current_ids}, "deleted_at": None}
    ):
        node.pop("_id", None)
        u = await database.users.find_one(
            {"membership_id": node["user_membership_id"], "deleted_at": None},
            {"full_name": 1, "state": 1, "city": 1, "mobile": 1},
        ) or {}
        # Active subscription check
        active_sub = await database.program_purchases.find_one(
            {
                "user_membership_id": node["user_membership_id"],
                "source": {"$in": ["subscription_mock"]},
                "status": "active",
                "deleted_at": None,
            }
        )
        meter = await get_meter(database, node["user_membership_id"])
        items.append(
            {
                "membership_id": node["user_membership_id"],
                "full_name": u.get("full_name"),
                "state": u.get("state"),
                "city": u.get("city"),
                "joining_date": node.get("joining_date"),
                "status": node.get("status", "active"),
                "has_subscription": bool(active_sub),
                "activity_status": meter.get("status"),
            }
        )
    return {"items": items, "level": level, "count": len(items)}


# ---------------- Admin --------------------------------------------------


@router.get("/admin/settings")
async def admin_settings_get(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    keys = [
        "commission_l1_percent",
        "commission_l2_percent",
        "commission_l3_percent",
        "commission_l1_fixed",
        "commission_l2_fixed",
        "commission_l3_fixed",
        "commission_mode",
        "grace_period_days",
        "activity_sessions_required",
    ]
    out: dict = {}
    for k in keys:
        row = await database.app_settings.find_one({"key": k, "deleted_at": None})
        out[k] = (row or {}).get("value")
    # Defaults from env
    out.setdefault("commission_l1_percent", settings.COMMISSION_L1_PERCENT)
    out.setdefault("commission_l2_percent", settings.COMMISSION_L2_PERCENT)
    out.setdefault("commission_l3_percent", settings.COMMISSION_L3_PERCENT)
    out.setdefault("commission_mode", "percent")
    out.setdefault("grace_period_days", 3)
    out.setdefault("activity_sessions_required", settings.ACTIVITY_SESSIONS_REQUIRED)
    return out


@router.put("/admin/settings")
async def admin_settings_put(
    body: ReferralSettingsUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    from datetime import datetime, timezone
    import uuid

    now = datetime.now(timezone.utc).isoformat()
    for k, v in body.model_dump(exclude_none=True).items():
        await database.app_settings.update_one(
            {"key": k},
            {
                "$set": {"value": v, "updated_at": now},
                "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now, "deleted_at": None},
            },
            upsert=True,
        )
    return await admin_settings_get(database, _admin={})  # type: ignore[arg-type]
