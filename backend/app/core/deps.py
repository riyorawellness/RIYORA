"""FastAPI dependencies: DB handle + auth guards."""
from fastapi import Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import decode_token
from app.db.mongo import get_db


def db() -> AsyncIOMotorDatabase:
    return get_db()


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


async def get_current_user(
    authorization: str | None = Header(default=None),
    database: AsyncIOMotorDatabase = Depends(db),
) -> dict:
    token = _extract_bearer(authorization)
    try:
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    if payload.get("role") != "user":
        raise HTTPException(status_code=403, detail="Not a user token")
    user = await database.users.find_one({"membership_id": payload["sub"], "deleted_at": None})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_admin(
    authorization: str | None = Header(default=None),
    database: AsyncIOMotorDatabase = Depends(db),
) -> dict:
    token = _extract_bearer(authorization)
    try:
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e
    if payload.get("type") != "access" or payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    admin = await database.admins.find_one({"mobile": payload["sub"], "deleted_at": None})
    if not admin:
        raise HTTPException(status_code=401, detail="Admin not found")
    return admin
