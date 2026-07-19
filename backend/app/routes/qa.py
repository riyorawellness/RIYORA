"""QA / Business Rule Validation route + Live integration checks."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.deps import db, get_current_admin
from app.services.brv import build_pdf, run_brv
from app.services import payment as pay_svc
from app.services import firebase_auth as fb
from app.utils.audit import log_action

logger = logging.getLogger(__name__)
_settings = get_settings()

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


# =============================================================================
# LIVE INTEGRATION CHECKS
# =============================================================================
# Diagnostics for verifying that Razorpay + MSG91 are correctly wired to live
# credentials BEFORE flipping production. All endpoints are admin-only and
# non-destructive (test order is ₹1 and never captured / verified).


def _mask(value: str, keep: int = 4) -> str:
    """Return "abcd…wxyz" style masked value for safe display."""
    if not value:
        return ""
    s = str(value)
    if len(s) <= keep * 2:
        return s[0] + "…" + s[-1]
    return f"{s[:keep]}…{s[-keep:]}"


@router.get("/live-check/status")
async def live_check_status(_admin: dict = Depends(get_current_admin)):
    """One-shot health snapshot of every launch-critical integration."""
    rzp_key = _settings.RAZORPAY_KEY_ID or ""
    rzp_secret = _settings.RAZORPAY_KEY_SECRET or ""
    rzp_webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    is_live_key = rzp_key.startswith("rzp_live_")

    # Firebase readiness
    fb_configured = False
    fb_project = os.environ.get("FIREBASE_PROJECT_ID", "")
    try:
        fb._init()
        fb_configured = True
    except Exception:  # noqa: BLE001
        fb_configured = False

    return {
        "razorpay": {
            "mock_mode": _settings.RAZORPAY_MOCK_MODE,
            "is_mock_effective": pay_svc.is_mock(),
            "key_id_masked": _mask(rzp_key),
            "key_id_prefix": rzp_key[:8] if rzp_key else "",
            "is_live_key": is_live_key,
            "has_secret": bool(rzp_secret),
            "has_webhook_secret": bool(rzp_webhook_secret),
            "webhook_url_hint": "/api/payments/webhook  ·  /api/payments/razorpay/webhook",
            "status": "live" if (is_live_key and not _settings.RAZORPAY_MOCK_MODE) else "mock",
        },
        "firebase": {
            "configured": fb_configured,
            "project_id": fb_project,
            "status": "live" if fb_configured else "not_configured",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


class RazorpayTestOrderRequest(BaseModel):
    amount_paise: int = Field(default=100, ge=100, le=100000)
    receipt_note: str | None = Field(default=None, max_length=40)


@router.post("/live-check/razorpay/test-order")
async def live_check_razorpay_test_order(
    body: RazorpayTestOrderRequest,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    """Create a real ₹1 (or configurable) test order.

    Non-destructive: no purchase row is created, no user is charged. In LIVE
    mode this hits the actual Razorpay REST API and returns the real order id;
    in MOCK mode it returns a synthetic order id. Either way admins can then
    use the returned order id + key_id from `/config` to test the checkout
    modal end-to-end without wiring it to a user or program.
    """
    receipt = f"livecheck_{uuid.uuid4().hex[:10]}"
    try:
        order = pay_svc.create_order(
            amount_paise=int(body.amount_paise),
            receipt=receipt,
            notes={
                "diagnostic": "live-check",
                "admin_mobile": admin["mobile"],
                "note": (body.receipt_note or "")[:40],
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Razorpay live-check failed: %s", exc)
        # Return raw error string so admin can copy-paste to support.
        raise HTTPException(502, f"Razorpay error: {exc}") from exc

    await log_action(
        database, actor_id=admin["mobile"], action="qa.live_check.razorpay_order",
        entity="qa", meta={"order_id": order.get("id"), "amount": body.amount_paise, "is_mock": order.get("is_mock", pay_svc.is_mock())},
    )
    return {
        "success": True,
        "order_id": order.get("id"),
        "amount_paise": order.get("amount"),
        "currency": order.get("currency", "INR"),
        "receipt": order.get("receipt"),
        "is_mock": bool(order.get("is_mock", pay_svc.is_mock())),
        "key_id": pay_svc.key_id_for_frontend(),
        "notes": order.get("notes", {}),
        "raw_status": order.get("status", ""),
    }


@router.get("/live-check/webhook-events")
async def live_check_webhook_events(
    limit: int = 25,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Return recent Razorpay webhook events observed by the backend.

    Sourced from `activity_log` rows written by `POST /api/payments/webhook`
    with action prefixes `razorpay.webhook.*`. Useful to confirm the Razorpay
    dashboard is actually reaching this deployment.
    """
    limit = max(1, min(int(limit or 25), 100))
    cursor = database.activity_log.find(
        {"action": {"$regex": r"^razorpay\.webhook\."}}
    ).sort("created_at", -1).limit(limit)
    events = []
    async for row in cursor:
        row.pop("_id", None)
        events.append({
            "id": row.get("id"),
            "event": (row.get("action") or "").replace("razorpay.webhook.", ""),
            "target": row.get("target"),
            "meta": row.get("meta") or {},
            "created_at": row.get("created_at"),
        })
    return {"events": events, "count": len(events)}


# Events the Razorpay dashboard MUST be configured to send in order for both
# one-time payments and subscription (AutoPay/UPI mandate) flows to work.
REQUIRED_RAZORPAY_EVENTS = [
    # One-time payments
    "payment.captured",
    "order.paid",
    "payment.failed",
    # Subscriptions
    "subscription.authenticated",
    "subscription.charged",
    "subscription.completed",
    "subscription.cancelled",
    "subscription.halted",
    "subscription.pending",
]


@router.get("/live-check/webhook-coverage")
async def live_check_webhook_coverage(
    lookback_days: int = 30,
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Report which required Razorpay events have been received recently.

    Returns a checklist of `REQUIRED_RAZORPAY_EVENTS` with a `seen` flag and
    `last_seen_at` timestamp per event. Admins use this to confirm the
    Razorpay dashboard webhook subscription is fully configured.
    """
    lookback_days = max(1, min(int(lookback_days or 30), 365))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    seen_map: dict[str, str] = {}
    cursor = database.activity_log.find(
        {
            "action": {"$regex": r"^razorpay\.webhook\."},
            "created_at": {"$gte": cutoff},
        }
    ).sort("created_at", -1)
    async for row in cursor:
        event_name = (row.get("action") or "").replace("razorpay.webhook.", "")
        if event_name and event_name not in seen_map:
            seen_map[event_name] = row.get("created_at")

    checklist = []
    for name in REQUIRED_RAZORPAY_EVENTS:
        checklist.append({
            "event": name,
            "seen": name in seen_map,
            "last_seen_at": seen_map.get(name),
            "category": "subscription" if name.startswith("subscription.") else "one_time",
        })

    return {
        "lookback_days": lookback_days,
        "required_events": REQUIRED_RAZORPAY_EVENTS,
        "checklist": checklist,
        "extra_events_seen": sorted(set(seen_map.keys()) - set(REQUIRED_RAZORPAY_EVENTS)),
        "webhook_paths": [
            "/api/payments/webhook",
            "/api/payments/razorpay/webhook",
        ],
    }


# ------------------------- Referral Engine Audit ------------------------------

@router.get("/referral-audit")
async def referral_audit_json(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Full referral engine audit — returns structured JSON with pass/fail
    per check + headline stats. Safe to call anytime; read-only."""
    from app.services.referral_audit import run_referral_audit
    return await run_referral_audit(database)


@router.get("/referral-audit.pdf")
async def referral_audit_pdf(
    database: AsyncIOMotorDatabase = Depends(db),
    _admin: dict = Depends(get_current_admin),
):
    """Same audit as JSON, delivered as a printable PDF."""
    from fastapi.responses import Response
    from app.services.referral_audit import build_pdf, run_referral_audit
    report = await run_referral_audit(database)
    pdf_bytes = build_pdf(report)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="referral-audit.pdf"'},
    )

