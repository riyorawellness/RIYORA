"""Backup & Restore service for MongoDB.

Uses `mongodump --archive --gzip` to produce a single-file backup that is
easy to move, restore, or ship off-box. Files land in `BACKUP_DIR` (default
`/app/backups`).
"""
from __future__ import annotations

import asyncio
import os
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

settings = get_settings()

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/app/backups"))


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _ensure_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _db_name() -> str:
    return os.environ.get("DB_NAME") or getattr(settings, "DB_NAME", "test_database")


def _mongo_uri() -> str:
    return os.environ.get("MONGO_URL") or getattr(settings, "MONGO_URL", "mongodb://localhost:27017")


async def _run(cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


async def create_backup(reason: str = "manual") -> dict:
    """Run mongodump and return backup metadata."""
    _ensure_dir()
    stamp = _now_stamp()
    safe_reason = "".join(c if c.isalnum() or c == "_" else "_" for c in reason)[:32]
    filename = f"riyora-{_db_name()}-{stamp}-{safe_reason}.archive.gz"
    dest = BACKUP_DIR / filename

    cmd = (
        f"mongodump --uri={shlex.quote(_mongo_uri())} "
        f"--db={shlex.quote(_db_name())} "
        f"--archive={shlex.quote(str(dest))} --gzip --quiet"
    )
    code, _out, err = await _run(cmd, timeout=600)
    if code != 0 or not dest.exists():
        raise RuntimeError(f"mongodump failed (exit {code}): {err.strip()[:400]}")

    size = dest.stat().st_size
    return {
        "filename": filename,
        "path": str(dest),
        "size_bytes": size,
        "size_human": _human_size(size),
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def list_backups() -> list[dict]:
    _ensure_dir()
    items = []
    for p in sorted(
        BACKUP_DIR.glob("*.archive.gz"),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    ):
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        items.append(
            {
                "filename": p.name,
                "size_bytes": st.st_size,
                "size_human": _human_size(st.st_size),
                "created_at": datetime.fromtimestamp(
                    st.st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return items


async def restore_backup(filename: str, drop: bool = True) -> dict:
    """Restore a specific backup archive. When `drop=True`, existing
    collections are wiped before restore (destructive but consistent)."""
    _ensure_dir()
    # Reject any path traversal.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("Invalid backup filename")
    src = BACKUP_DIR / filename
    if not src.exists():
        raise FileNotFoundError(filename)

    drop_flag = " --drop" if drop else ""
    cmd = (
        f"mongorestore --uri={shlex.quote(_mongo_uri())} "
        f"--nsInclude={shlex.quote(_db_name())}.\\* "
        f"--archive={shlex.quote(str(src))} --gzip{drop_flag} --quiet"
    )
    code, _out, err = await _run(cmd, timeout=900)
    if code != 0:
        raise RuntimeError(
            f"mongorestore failed (exit {code}): {err.strip()[:400]}"
        )
    return {
        "filename": filename,
        "restored_at": datetime.now(timezone.utc).isoformat(),
    }


def delete_backup(filename: str) -> bool:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("Invalid backup filename")
    src = BACKUP_DIR / filename
    if not src.exists():
        return False
    src.unlink()
    return True


async def _pretty_summary_size(reason: str = "manual") -> Optional[str]:
    """Debug helper — not used in production."""
    return None
