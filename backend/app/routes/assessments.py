"""Assessments — user list/get by module; admin CRUD.

Phase 4 additions:
  * `randomize` option — questions shuffled per fetch (server-side).
  * Attempt-limit enforcement using `attempts_allowed` (from admin) counted
    against past assessment_results for the same user + assessment.
  * `passed` submissions auto-issue the program certificate if all modules done.
"""
from datetime import datetime, timezone
import random
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_admin, get_current_user
from app.models.phase2 import (
    AssessmentCreate,
    AssessmentResultCreate,
    AssessmentUpdate,
    PaginatedResponse,
)
from app.repositories.base import BaseRepository
from app.services.program_engine import issue_certificate_if_eligible

router = APIRouter(prefix="/assessments", tags=["Assessments"])


def _repo(database: AsyncIOMotorDatabase) -> BaseRepository:
    return BaseRepository(database, "assessments", ["title"], "-created_at")


@router.get("", response_model=PaginatedResponse)
async def list_assessments(
    database: AsyncIOMotorDatabase = Depends(db),
    _current: dict = Depends(get_current_user),
    program_id: str | None = Query(default=None),
    module_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str = Query(default="-created_at"),
):
    filters = {}
    if program_id:
        filters["program_id"] = program_id
    if module_id:
        filters["module_id"] = module_id
    return await _repo(database).list_paginated(filters, search, sort, page, page_size)


@router.get("/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    doc = await _repo(database).get(assessment_id)
    if not doc:
        raise HTTPException(404, "Assessment not found")

    # Attempts summary
    total_attempts = await database.assessment_results.count_documents(
        {"assessment_id": assessment_id, "user_membership_id": current["membership_id"]}
    )
    passed_before = await database.assessment_results.find_one(
        {
            "assessment_id": assessment_id,
            "user_membership_id": current["membership_id"],
            "passed": True,
        }
    )
    attempts_allowed = int(doc.get("attempts_allowed", 3))
    can_attempt = bool(passed_before) or total_attempts < attempts_allowed

    questions = list(doc.get("questions") or [])
    if doc.get("randomize"):
        # Deterministic per attempt so preview/submit stay aligned: seed by
        # (user, assessment, attempt#).
        seed = f"{current['membership_id']}:{assessment_id}:{total_attempts}"
        rng = random.Random(seed)
        rng.shuffle(questions)

    # Strip correct_index from what we send to the client.
    safe_questions = [{"question": q["question"], "options": q["options"]} for q in questions]
    return {
        **doc,
        "questions": safe_questions,
        "attempts_used": total_attempts,
        "attempts_allowed": attempts_allowed,
        "can_attempt": can_attempt,
        "already_passed": bool(passed_before),
    }


@router.post("/{assessment_id}/submit")
async def submit_assessment(
    assessment_id: str,
    body: AssessmentResultCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
):
    assessment = await database.assessments.find_one({"id": assessment_id, "deleted_at": None})
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    questions = assessment.get("questions", [])
    if len(body.answers) != len(questions):
        raise HTTPException(400, "Answer count must match question count")

    # Attempt-limit gate (skip if already passed).
    already_passed = await database.assessment_results.find_one(
        {
            "assessment_id": assessment_id,
            "user_membership_id": current["membership_id"],
            "passed": True,
        }
    )
    if not already_passed:
        used = await database.assessment_results.count_documents(
            {"assessment_id": assessment_id, "user_membership_id": current["membership_id"]}
        )
        allowed = int(assessment.get("attempts_allowed", 3))
        if used >= allowed:
            raise HTTPException(429, f"No attempts remaining ({used}/{allowed})")

    marks = sum(1 for i, q in enumerate(questions) if body.answers[i] == q.get("correct_index"))
    passed = marks >= assessment.get("passing_marks", 0)
    doc = {
        "id": str(uuid.uuid4()),
        "assessment_id": assessment_id,
        "user_membership_id": current["membership_id"],
        "program_id": assessment.get("program_id"),
        "answers": body.answers,
        "marks": marks,
        "total": len(questions),
        "passed": passed,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    await database.assessment_results.insert_one(doc)
    doc.pop("_id", None)

    # If passed, try to auto-issue certificate for the parent program.
    certificate = None
    if passed and assessment.get("program_id"):
        certificate = await issue_certificate_if_eligible(
            database, current["membership_id"], assessment["program_id"]
        )
    return {"result": doc, "certificate": certificate}


@router.get("/{assessment_id}/results/me", response_model=PaginatedResponse)
async def my_results(
    assessment_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    current: dict = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    # Note: assessment_results docs don't have deleted_at → override:
    query = {"assessment_id": assessment_id, "user_membership_id": current["membership_id"]}
    total = await database.assessment_results.count_documents(query)
    cursor = (
        database.assessment_results.find(query)
        .sort("submitted_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    async for d in cursor:
        d.pop("_id", None)
        items.append(d)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# ------------------------- Admin ------------------------------------------
@router.post("/admin", status_code=201)
async def admin_create_assessment(
    body: AssessmentCreate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    if not await database.program_modules.find_one({"id": body.module_id, "deleted_at": None}):
        raise HTTPException(400, "module_id does not exist")
    if not await database.programs.find_one({"id": body.program_id, "deleted_at": None}):
        raise HTTPException(400, "program_id does not exist")
    # Validate correct_index inside options range
    for q in body.questions:
        if q.correct_index >= len(q.options):
            raise HTTPException(400, "correct_index out of range for one of the questions")
    exists = await database.assessments.find_one({"module_id": body.module_id, "deleted_at": None})
    if exists:
        raise HTTPException(409, "Assessment already exists for this module")
    payload = body.model_dump()
    payload["questions"] = [q.model_dump() if hasattr(q, "model_dump") else q for q in payload["questions"]]
    return await _repo(database).create(payload, actor=admin["mobile"])


@router.put("/admin/{assessment_id}")
async def admin_update_assessment(
    assessment_id: str,
    body: AssessmentUpdate,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    updates = body.model_dump(exclude_none=True)
    if "questions" in updates:
        for q in updates["questions"]:
            if q["correct_index"] >= len(q["options"]):
                raise HTTPException(400, "correct_index out of range for one of the questions")
    updated = await _repo(database).update(assessment_id, updates, actor=admin["mobile"])
    if not updated:
        raise HTTPException(404, "Assessment not found")
    return updated


@router.delete("/admin/{assessment_id}")
async def admin_delete_assessment(
    assessment_id: str,
    database: AsyncIOMotorDatabase = Depends(db),
    admin: dict = Depends(get_current_admin),
):
    ok = await _repo(database).soft_delete(assessment_id, actor=admin["mobile"])
    if not ok:
        raise HTTPException(404, "Assessment not found")
    return {"message": "Assessment deleted"}
