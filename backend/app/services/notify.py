"""Notification triggers — 2026-02 launch spec.

One helper for all in-app notification inserts, plus wrappers for the
7 auto-triggers required by pre-launch checklist:

  1. Payment Success          (Razorpay verify + Manual QR approved)
  2. Payment Failed           (Razorpay verify failed + Manual QR rejected)
  3. New Module Unlocked      (fired from `mark_module_completed`)
  4. Validity Expiring        (7/3/1 day windows — batched via cron endpoint)
  5. Subscription Renewal     (Inner Peace subscription renewal — future)
  6. Referral Income          (commission engine on payout create)
  7. New Program              (broadcast when admin creates/activates a program)

Every call is best-effort — a notification insert must NEVER fail the parent
business operation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def notify(
    db: AsyncIOMotorDatabase,
    *,
    membership_id: str,
    title: str,
    body: str,
    category: str = "system",
    cta_link: str | None = None,
    cta_label: str | None = None,
    meta: dict | None = None,
    dedup_key: str | None = None,
) -> Optional[dict]:
    """Insert a single in-app notification. Never raises on failure.

    If `dedup_key` is provided, skip insert when a live notification with the
    same key already exists for the user (used by validity-expiring windows
    to avoid daily spam).
    """
    try:
        if dedup_key:
            existing = await db.notifications.find_one(
                {
                    "user_membership_id": membership_id,
                    "meta.dedup_key": dedup_key,
                    "deleted_at": None,
                }
            )
            if existing:
                return None
        doc = {
            "id": str(uuid.uuid4()),
            "user_membership_id": membership_id,
            "title": title,
            "body": body,
            "category": category,
            "is_broadcast": False,
            "is_read": False,
            "cta_link": cta_link,
            "cta_label": cta_label,
            "meta": {**(meta or {}), **({"dedup_key": dedup_key} if dedup_key else {})},
            "created_at": _now(),
            "updated_at": _now(),
            "deleted_at": None,
        }
        await db.notifications.insert_one(doc)
        doc.pop("_id", None)
        return doc
    except Exception:  # noqa: BLE001
        return None


async def broadcast(
    db: AsyncIOMotorDatabase,
    *,
    title: str,
    body: str,
    category: str = "system",
    cta_link: str | None = None,
    meta: dict | None = None,
) -> int:
    """Fan-out broadcast: one notification row per active user. Returns count
    of rows inserted. Mirrors the admin broadcast endpoint's persistence
    strategy so the standard `/notifications/me` list picks them up."""
    try:
        now = _now()
        base = {
            "title": title,
            "body": body,
            "category": category,
            "cta_link": cta_link,
            "is_broadcast": True,
            "is_read": False,
            "meta": meta or {},
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        docs = []
        async for u in db.users.find(
            {"deleted_at": None}, {"membership_id": 1}
        ):
            mid = u.get("membership_id")
            if not mid:
                continue
            docs.append({**base, "id": str(uuid.uuid4()), "user_membership_id": mid})
        if not docs:
            return 0
        await db.notifications.insert_many(docs)
        return len(docs)
    except Exception:  # noqa: BLE001
        return 0


# ---------- Named triggers (thin wrappers) -----------------------------------

async def payment_success(
    db, *, membership_id: str, program_name: str, amount: float, source: str = "razorpay"
):
    return await notify(
        db,
        membership_id=membership_id,
        title="Payment successful",
        body=f"₹{amount:,.2f} paid for {program_name} via {source.upper()}. "
        "Your program is now unlocked.",
        category="payment",
        cta_link="/app/payment-history",
        meta={"program_name": program_name, "amount": amount, "source": source},
    )


async def payment_failed(
    db, *, membership_id: str, program_name: str, reason: str = ""
):
    return await notify(
        db,
        membership_id=membership_id,
        title="Payment failed",
        body=(
            f"Your payment for {program_name} could not be verified. "
            + (reason or "You can retry from the program page anytime.")
        ),
        category="payment",
        cta_link="/app/payment-history",
    )


async def module_unlocked(
    db, *, membership_id: str, program_name: str, module_name: str, module_id: str
):
    return await notify(
        db,
        membership_id=membership_id,
        title="New module unlocked",
        body=f"{module_name} is now available in {program_name}.",
        category="progress",
        cta_link=f"/app/programs",
        meta={"module_id": module_id},
        dedup_key=f"unlock:{module_id}:{membership_id}",
    )


async def referral_income(
    db, *, sponsor_mid: str, buyer_name: str, amount: float, level: int
):
    return await notify(
        db,
        membership_id=sponsor_mid,
        title=f"₹{amount:,.2f} referral income",
        body=(
            f"You earned level-{level} commission from {buyer_name}'s purchase. "
            "Withdraw from wallet anytime after approval."
        ),
        category="referral",
        cta_link="/app/wallet",
        meta={"level": level, "amount": amount, "buyer_name": buyer_name},
    )


async def validity_expiring(
    db,
    *,
    membership_id: str,
    program_name: str,
    program_id: str,
    days_left: int,
    expiry_date: str,
):
    return await notify(
        db,
        membership_id=membership_id,
        title=f"Access expires in {days_left} day{'s' if days_left != 1 else ''}",
        body=(
            f"Your {program_name} access ends on {expiry_date[:10]}. "
            "Tap Renew to keep your progress and referral eligibility."
        ),
        category="validity",
        # Direct-to-payment so renewal is one tap away.
        cta_link=f"/app/pay/{program_id}",
        cta_label="Renew",
        dedup_key=f"expiring:{program_id}:{membership_id}:{days_left}",
        meta={"program_id": program_id, "days_left": days_left, "renew": True},
    )


async def new_program_published(
    db, *, program_name: str, program_id: str
):
    return await broadcast(
        db,
        title="New program available",
        body=f"{program_name} is now live in the RIYORA library — check it out!",
        category="announcement",
        cta_link=f"/app/programs/{program_id}",
        meta={"program_id": program_id},
    )
