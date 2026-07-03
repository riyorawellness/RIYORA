"""Pydantic v2 request/response schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MOBILE_REGEX = r"^[6-9]\d{9}$"  # Indian 10-digit mobile


class MobileOnly(BaseModel):
    mobile: str = Field(..., pattern=MOBILE_REGEX)


class SendOtpRequest(MobileOnly):
    purpose: Literal["register", "forgot_password"]


class VerifyOtpRequest(MobileOnly):
    purpose: Literal["register", "forgot_password"]
    code: str = Field(..., min_length=4, max_length=8)


class ValidateReferralRequest(BaseModel):
    referral_id: str = Field(..., pattern=r"^RW\d{6}$")


class ReferralInfo(BaseModel):
    referral_id: str
    sponsor_name: str
    sponsor_membership_id: str


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    mobile: str = Field(..., pattern=MOBILE_REGEX)
    state: str = Field(..., min_length=2, max_length=60)
    city: str = Field(..., min_length=2, max_length=60)
    referral_id: str = Field(..., pattern=r"^RW\d{6}$")
    password: str = Field(..., min_length=8, max_length=72)
    confirm_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("confirm_password")
    @classmethod
    def _match(cls, v, info):
        if info.data.get("password") != v:
            raise ValueError("Passwords do not match")
        return v


class LoginRequest(BaseModel):
    mobile: str = Field(..., pattern=MOBILE_REGEX)
    password: str = Field(..., min_length=8, max_length=72)


class ResetPasswordRequest(BaseModel):
    mobile: str = Field(..., pattern=MOBILE_REGEX)
    new_password: str = Field(..., min_length=8, max_length=72)
    confirm_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("confirm_password")
    @classmethod
    def _match(cls, v, info):
        if info.data.get("new_password") != v:
            raise ValueError("Passwords do not match")
        return v


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


class OtpSentResponse(BaseModel):
    message: str
    expires_in_seconds: int
    dev_code: str | None = None
