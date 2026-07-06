"""Program Engine — the business-logic brain for Phase 4.

Encapsulates:
  * Program-sequence gating (Level N requires Level N-1 completed + cert)
  * Sequential module unlock (Module N requires Module N-1 completed)
  * Progress computation (percentage, last_accessed, completed_date)
  * Auto certificate issue when all modules + assessment passed
  * Category resolution for the user dashboard
    (purchased | locked | completed | expired | available)
"""
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.validity import get_active_purchase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------- program sequence -----------------------------


async def _prev_level_program(
    db: AsyncIOMotorDatabase, program: dict
) -> Optional[dict]:
    """Return the level-1 program that must be completed before this one, or None
    if this program has no prerequisite (subscription or level<=1)."""
    lvl = program.get("level")
    if not isinstance(lvl, int) or lvl <= 1:
        return None
    prev = await db.programs.find_one(
        {"level": lvl - 1, "deleted_at": None, "is_active": True}
    )
    if prev:
        prev.pop("_id", None)
    return prev


async def is_program_completed_with_certificate(
    db: AsyncIOMotorDatabase, user_membership_id: str, program_id: str
) -> bool:
    prog = await db.program_progress.find_one(
        {"user_membership_id": user_membership_id, "program_id": program_id, "deleted_at": None}
    )
    if not prog or not prog.get("certificate_eligible"):
        return False
    cert = await db.certificates.find_one(
        {
            "user_membership_id": user_membership_id,
            "program_id": program_id,
            "status": "issued",
            "deleted_at": None,
        }
    )
    return bool(cert)


async def check_purchase_allowed(
    db: AsyncIOMotorDatabase, user_membership_id: str, program: dict
) -> tuple[bool, str]:
    """Enforce the Level 1 → Level 5 chain (subscriptions bypass this)."""
    if program.get("is_subscription"):
        return True, ""
    prev = await _prev_level_program(db, program)
    if prev is None:
        return True, ""
    ok = await is_program_completed_with_certificate(db, user_membership_id, prev["id"])
    if ok:
        return True, ""
    return False, f"Complete '{prev['name']}' and earn its certificate before purchasing this program."


# --------------------------- module unlock --------------------------------


async def is_module_unlocked(
    db: AsyncIOMotorDatabase,
    user_membership_id: str,
    program_id: str,
    module: dict,
) -> bool:
    # Program-level access mode overrides everything: 'free' means all modules
    # are unlocked once the program is purchased.
    program = await db.programs.find_one(
        {"id": program_id, "deleted_at": None}, {"access_mode": 1, "_id": 0}
    )
    if program and program.get("access_mode") == "free":
        return True
    if not module.get("sequential_unlock", True):
        return True
    module_number = int(module.get("module_number", 1))
    # The FIRST module in the program (lowest module_number, regardless of
    # its actual value) is always the entry point — otherwise buyers with a
    # program that starts at module_number 2 or 3 would be permanently
    # locked out.
    first_module = await db.program_modules.find_one(
        {"program_id": program_id, "deleted_at": None},
        sort=[("module_number", 1)],
        projection={"module_number": 1, "_id": 0},
    )
    if first_module and int(first_module.get("module_number", 1)) >= module_number:
        return True
    prog = await db.program_progress.find_one(
        {"user_membership_id": user_membership_id, "program_id": program_id, "deleted_at": None}
    )
    completed = set((prog or {}).get("completed_modules") or [])
    # Previous module id must be in completed_modules.
    prev = await db.program_modules.find_one(
        {
            "program_id": program_id,
            "module_number": module_number - 1,
            "deleted_at": None,
        }
    )
    if not prev:
        # If admin skipped a number, treat as unlocked.
        return True
    return prev["id"] in completed


# --------------------------- progress -------------------------------------


async def _all_modules(db: AsyncIOMotorDatabase, program_id: str) -> list[dict]:
    docs = []
    async for m in db.program_modules.find({"program_id": program_id, "deleted_at": None}).sort(
        "module_number", 1
    ):
        m.pop("_id", None)
        docs.append(m)
    return docs


async def _upsert_progress(
    db: AsyncIOMotorDatabase,
    user_membership_id: str,
    program_id: str,
    updates: dict,
    actor: Optional[str] = None,
) -> dict:
    now = _now_iso()
    set_on_insert = {
        "id": str(uuid.uuid4()),
        "user_membership_id": user_membership_id,
        "program_id": program_id,
        "created_at": now,
        "created_by": actor,
        "deleted_at": None,
    }
    for k in ("completed_modules", "percentage", "certificate_eligible"):
        if k not in updates:
            set_on_insert[k] = [] if k == "completed_modules" else (False if k == "certificate_eligible" else 0)

    result = await db.program_progress.find_one_and_update(
        {"user_membership_id": user_membership_id, "program_id": program_id, "deleted_at": None},
        {"$set": {**updates, "updated_at": now, "updated_by": actor}, "$setOnInsert": set_on_insert},
        upsert=True,
        return_document=True,
    )
    if result is not None:
        result.pop("_id", None)
    return result or {}


async def mark_module_completed(
    db: AsyncIOMotorDatabase,
    user_membership_id: str,
    program_id: str,
    module_id: str,
    time_spent_sec: int = 0,
) -> dict:
    """Idempotently marks a module completed and recomputes progress.

    Also flips `certificate_eligible=True` once all non-assessment modules are done.
    """
    module = await db.program_modules.find_one({"id": module_id, "program_id": program_id, "deleted_at": None})
    if not module:
        raise ValueError("Module not found")

    modules = await _all_modules(db, program_id)
    module_ids = {m["id"] for m in modules}
    if module_id not in module_ids:
        raise ValueError("Module does not belong to program")

    prog = await db.program_progress.find_one(
        {"user_membership_id": user_membership_id, "program_id": program_id, "deleted_at": None}
    )
    completed = list((prog or {}).get("completed_modules") or [])
    if module_id not in completed:
        completed.append(module_id)

    non_assessment = [m["id"] for m in modules if m.get("type") != "assessment"]
    non_assessment_or_all = non_assessment or [m["id"] for m in modules]
    completion_fraction = (
        len([m for m in non_assessment_or_all if m in completed]) / max(1, len(non_assessment_or_all))
    )
    percentage = round(completion_fraction * 100, 2)
    certificate_eligible = completion_fraction >= 1.0

    updates: dict[str, Any] = {
        "completed_modules": completed,
        "current_module_id": module_id,
        "percentage": percentage,
        "certificate_eligible": certificate_eligible,
        "last_accessed": _now_iso(),
        "time_spent_sec": int((prog or {}).get("time_spent_sec", 0) + max(0, int(time_spent_sec))),
    }
    if certificate_eligible:
        updates["completion_date"] = _now_iso()

    result = await _upsert_progress(db, user_membership_id, program_id, updates, actor=user_membership_id)

    # Auto-log activity session for ANY program (subscription or one-time)
    # on module completion. Session counts feed the rolling 30-day meter.
    try:
        from app.services.activity_meter import log_session as _log_session

        try:
            await _log_session(
                db,
                user_membership_id,
                source="module_complete",
                program_id=program_id,
                module_id=module_id,
            )
        except ValueError:
            # User has no active purchase — skip silently.
            pass
    except Exception:  # noqa: BLE001
        pass

    return result


# --------------------------- certificate ----------------------------------


async def issue_certificate_if_eligible(
    db: AsyncIOMotorDatabase, user_membership_id: str, program_id: str
) -> Optional[dict]:
    """Issue a certificate when the user has completed all modules and the
    program's assessment (if any) has been passed. Idempotent.
    """
    prog = await db.program_progress.find_one(
        {"user_membership_id": user_membership_id, "program_id": program_id, "deleted_at": None}
    )
    if not prog or not prog.get("certificate_eligible"):
        return None

    # If an assessment exists for the program, require at least one passed result.
    assessment = await db.assessments.find_one({"program_id": program_id, "deleted_at": None})
    if assessment:
        passed = await db.assessment_results.find_one(
            {
                "assessment_id": assessment["id"],
                "user_membership_id": user_membership_id,
                "passed": True,
            }
        )
        if not passed:
            return None

    # Already issued?
    existing = await db.certificates.find_one(
        {
            "user_membership_id": user_membership_id,
            "program_id": program_id,
            "status": "issued",
            "deleted_at": None,
        }
    )
    if existing:
        existing.pop("_id", None)
        return existing

    program = await db.programs.find_one({"id": program_id, "deleted_at": None})
    program_name = (program or {}).get("name") or program_id
    now = _now_iso()
    cert_number = f"RW-CERT-{uuid.uuid4().hex[:10].upper()}"
    verification_number = uuid.uuid4().hex[:16].upper()
    user_doc = await db.users.find_one({"membership_id": user_membership_id, "deleted_at": None})
    doc = {
        "id": str(uuid.uuid4()),
        "user_membership_id": user_membership_id,
        "user_name": (user_doc or {}).get("full_name"),
        "program_id": program_id,
        "program_name": program_name,
        "certificate_number": cert_number,
        "verification_number": verification_number,
        "issue_date": now,
        "completion_date": prog.get("completion_date") or now,
        "status": "issued",
        "pdf_url": None,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    await db.certificates.insert_one(doc)
    doc.pop("_id", None)
    return doc


# --------------------------- dashboard categorisation ---------------------


async def categorise_programs(
    db: AsyncIOMotorDatabase, user_membership_id: str
) -> dict[str, list[dict]]:
    """Group all active programs into user-facing buckets.

    Buckets:
      purchased  — active purchase, still within validity, not yet completed
      completed  — certificate issued
      expired    — has a past purchase whose expiry is in the past AND no active one
      locked     — sequence prerequisite not met
      available  — nothing purchased, prerequisite satisfied (or subscription)
    """
    now_iso = _now_iso()
    programs = []
    async for p in db.programs.find({"deleted_at": None, "is_active": True}).sort(
        [("order_index", 1), ("level", 1)]
    ):
        p.pop("_id", None)
        programs.append(p)

    buckets = {"purchased": [], "completed": [], "expired": [], "locked": [], "available": []}
    for p in programs:
        active = await get_active_purchase(db, user_membership_id, p["id"])
        completed = await is_program_completed_with_certificate(db, user_membership_id, p["id"])
        past = await db.program_purchases.find_one(
            {
                "user_membership_id": user_membership_id,
                "program_id": p["id"],
                "deleted_at": None,
            },
            sort=[("expiry_date", -1)],
        )
        prog_row = await db.program_progress.find_one(
            {"user_membership_id": user_membership_id, "program_id": p["id"], "deleted_at": None}
        )
        entry = {
            "program": p,
            "progress": {
                "percentage": (prog_row or {}).get("percentage", 0),
                "current_module_id": (prog_row or {}).get("current_module_id"),
                "certificate_eligible": (prog_row or {}).get("certificate_eligible", False),
                "last_accessed": (prog_row or {}).get("last_accessed"),
            },
            "active_purchase": active,
            "validity_remaining_days": _remaining_days(active.get("expiry_date")) if active else None,
        }

        if completed:
            buckets["completed"].append(entry)
        elif active:
            buckets["purchased"].append(entry)
        elif past and past.get("expiry_date") and past["expiry_date"] < now_iso:
            buckets["expired"].append(entry)
        else:
            allowed, _ = await check_purchase_allowed(db, user_membership_id, p)
            (buckets["available"] if allowed else buckets["locked"]).append(entry)

    return buckets


def _remaining_days(expiry_iso: Optional[str]) -> Optional[int]:
    if not expiry_iso:
        return None
    try:
        exp = datetime.fromisoformat(expiry_iso)
    except Exception:
        return None
    delta = exp - datetime.now(timezone.utc)
    return max(0, delta.days)


async def continue_learning(
    db: AsyncIOMotorDatabase, user_membership_id: str
) -> Optional[dict]:
    """Return the program the user should keep going with — most recently
    accessed non-completed active purchase.
    """
    cursor = db.program_progress.find(
        {"user_membership_id": user_membership_id, "deleted_at": None, "certificate_eligible": False}
    ).sort("last_accessed", -1).limit(1)
    async for prog in cursor:
        prog.pop("_id", None)
        active = await get_active_purchase(db, user_membership_id, prog["program_id"])
        if not active:
            continue
        program = await db.programs.find_one({"id": prog["program_id"], "deleted_at": None})
        if not program:
            continue
        program.pop("_id", None)
        current_module = None
        if prog.get("current_module_id"):
            current_module = await db.program_modules.find_one(
                {"id": prog["current_module_id"], "deleted_at": None}
            )
            if current_module:
                current_module.pop("_id", None)
        return {"program": program, "progress": prog, "current_module": current_module}
    return None
