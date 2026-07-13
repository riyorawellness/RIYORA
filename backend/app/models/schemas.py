"""Pydantic v2 request/response schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MOBILE_REGEX = r"^[6-9]\d{9}$"  # Indian 10-digit mobile


class MobileOnly(BaseModel):
    mobile: str = Field(..., pattern=MOBILE_REGEX)


class ValidateReferralRequest(BaseModel):
    referral_id: str = Field(..., pattern=r"^RW\d{6}$")


class ReferralInfo(BaseModel):
    referral_id: str
    sponsor_name: str
    sponsor_membership_id: str


class LoginRequest(BaseModel):
    """Legacy mobile+password login — deprecated; used only by
    /auth/firebase/link-existing under the hood via the security helpers."""
    mobile: str = Field(..., pattern=MOBILE_REGEX)
    password: str = Field(..., min_length=1, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    full_name: str
    mobile: str
    state: str
    city: str
    role: Literal["user", "admin"] = "user"
    membership_id: str
    referral_id: str
    sponsor_membership_id: str
    sponsor_name: str | None = None
    is_active: bool = True
    is_dummy: bool = False
    firebase_uid: str | None = None
    email: str | None = None
    email_verified: bool = False
    login_method: str | None = None
    photo_url: str | None = None
    last_login_at: str | None = None
    created_at: str
    updated_at: str


class AdminPublic(BaseModel):
    id: str
    name: str
    mobile: str
    role: Literal["admin"] = "admin"


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=60)
    city: str | None = Field(default=None, min_length=2, max_length=60)


class RefreshRequest(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str


