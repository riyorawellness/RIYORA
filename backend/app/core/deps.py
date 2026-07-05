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


async def get_current_user_or_admin(
    authorization: str | None = Header(default=None),
    database: AsyncIOMotorDatabase = Depends(db),
) -> dict:
    """Accepts either a user OR an admin access token.

    Used on read-only catalog endpoints (programs / modules) so the admin
    editor UI can fetch the same data without needing separate routes.
    Returns the user doc for user tokens, or the admin doc (with an
    ``is_admin=True`` flag) for admin tokens.
    """
    token = _extract_bearer(authorization)
    try:
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    role = payload.get("role")
    if role == "admin":
        admin = await database.admins.find_one({"mobile": payload["sub"], "deleted_at": None})
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        admin["is_admin"] = True
        return admin
    if role == "user":
        user = await database.users.find_one({"membership_id": payload["sub"], "deleted_at": None})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["is_admin"] = False
        return user
    raise HTTPException(status_code=403, detail="Unknown role")
