"""Generic repository with pagination, search, filter, sort and soft-delete.

Every Phase 2 route uses this to keep controllers thin.
"""
from datetime import datetime, timezone
from typing import Any
import re
import uuid

from motor.motor_asyncio import AsyncIOMotorDatabase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


class BaseRepository:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        collection: str,
        searchable_fields: list[str] | None = None,
        default_sort: str = "-created_at",
    ):
        self.db = db
        self.col = db[collection]
        self.searchable_fields = searchable_fields or []
        self.default_sort = default_sort

    # ------------------------ writes -----------------------------------------
    async def create(self, payload: dict, actor: str | None = None) -> dict:
        now = _now_iso()
        doc = {
            "id": str(uuid.uuid4()),
            **payload,
            "created_by": actor,
            "updated_by": actor,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        await self.col.insert_one(doc)
        return _clean(doc)

    async def update(self, doc_id: str, updates: dict, actor: str | None = None) -> dict | None:
        updates = {k: v for k, v in updates.items() if v is not None}
        if not updates:
            return await self.get(doc_id)
        updates["updated_at"] = _now_iso()
        updates["updated_by"] = actor
        result = await self.col.find_one_and_update(
            {"id": doc_id, "deleted_at": None},
            {"$set": updates},
            return_document=True,
        )
        return _clean(result)

    async def soft_delete(self, doc_id: str, actor: str | None = None) -> bool:
        result = await self.col.update_one(
            {"id": doc_id, "deleted_at": None},
            {"$set": {"deleted_at": _now_iso(), "updated_by": actor}},
        )
        return result.modified_count == 1

    async def restore(self, doc_id: str) -> bool:
        result = await self.col.update_one(
            {"id": doc_id, "deleted_at": {"$ne": None}},
            {"$set": {"deleted_at": None, "updated_at": _now_iso()}},
        )
        return result.modified_count == 1

    # ------------------------ reads ------------------------------------------
    async def get(self, doc_id: str) -> dict | None:
        return _clean(await self.col.find_one({"id": doc_id, "deleted_at": None}))

    async def get_by(self, filters: dict) -> dict | None:
        filters = {**filters, "deleted_at": None}
        return _clean(await self.col.find_one(filters))

    async def list_paginated(
        self,
        filters: dict | None = None,
        search: str | None = None,
        sort: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        page = max(1, int(page))
        page_size = min(max(1, int(page_size)), 200)
        query: dict[str, Any] = {"deleted_at": None, **(filters or {})}

        if search and self.searchable_fields:
            regex = {"$regex": re.escape(search), "$options": "i"}
            query["$or"] = [{f: regex} for f in self.searchable_fields]

        sort_spec = self._parse_sort(sort or self.default_sort)

        total = await self.col.count_documents(query)
        cursor = self.col.find(query).sort(sort_spec).skip((page - 1) * page_size).limit(page_size)
        items = [_clean(d) async for d in cursor]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    @staticmethod
    def _parse_sort(sort: str) -> list[tuple[str, int]]:
        """Accepts '-created_at,name' style. Prefix '-' = descending."""
        pairs: list[tuple[str, int]] = []
        for part in sort.split(","):
            part = part.strip()
            if not part:
                continue
            direction = -1 if part.startswith("-") else 1
            field = part.lstrip("-+")
            pairs.append((field, direction))
        return pairs or [("created_at", -1)]
