"""Membership routes: referral validation & lookup."""
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import db, get_current_user
from app.models.schemas import ReferralInfo, ValidateReferralRequest

router = APIRouter(prefix="/membership", tags=["Membership"])


@router.post("/validate-referral", response_model=ReferralInfo)
async def validate_referral(body: ValidateReferralRequest, database: AsyncIOMotorDatabase = Depends(db)):
    m = await database.memberships.find_one({"membership_id": body.referral_id, "deleted_at": None})
    if not m or not m.get("is_active", True):
        raise HTTPException(status_code=404, detail="Invalid Referral ID")
    return ReferralInfo(
        referral_id=m["membership_id"],
        sponsor_name=m.get("owner_name") or "RIYORA Wellness",
        sponsor_membership_id=m["membership_id"],
    )


@router.get("/me", response_model=dict)
async def my_membership(current: dict = Depends(get_current_user)):
    return {
        "membership_id": current["membership_id"],
        "referral_id": current["membership_id"],
        "sponsor_membership_id": current["sponsor_membership_id"],
        "sponsor_name": current.get("sponsor_name"),
        "full_name": current["full_name"],
        "is_active": current.get("is_active", True),
        "created_at": current["created_at"],
    }
