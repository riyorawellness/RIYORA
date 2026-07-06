"""Phase 6 — Refer & Earn Engine schemas."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Commission ----------------------------------------------------


class CommissionOverride(BaseModel):
    """Per-program commission override. If any field is set, it overrides the
    global default for that level. Admin can toggle mode = 'percent' or 'fixed'
    or 'both' (adds fixed + percent).
    """

    mode: Literal["percent", "fixed", "both"] = "percent"
    l1_percent: Optional[float] = Field(default=None, ge=0, le=100)
    l2_percent: Optional[float] = Field(default=None, ge=0, le=100)
    l3_percent: Optional[float] = Field(default=None, ge=0, le=100)
    l1_fixed: Optional[float] = Field(default=None, ge=0)
    l2_fixed: Optional[float] = Field(default=None, ge=0)
    l3_fixed: Optional[float] = Field(default=None, ge=0)


class CommissionAdminAction(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------- Payouts --------------------------------------------------------


class PayoutCreate(BaseModel):
    user_membership_id: str = Field(pattern=r"^RW\d{6}$")
    commission_ids: list[str] = Field(min_length=1)
    method: Literal["bank", "upi", "manual"] = "bank"
    reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=500)


class PayoutMarkPaid(BaseModel):
    reference: str = Field(min_length=1, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=500)


# ---------- Referral settings ---------------------------------------------


class ReferralSettingsUpdate(BaseModel):
    commission_l1_percent: Optional[float] = Field(default=None, ge=0, le=100)
    commission_l2_percent: Optional[float] = Field(default=None, ge=0, le=100)
    commission_l3_percent: Optional[float] = Field(default=None, ge=0, le=100)
    commission_l1_fixed: Optional[float] = Field(default=None, ge=0)
    commission_l2_fixed: Optional[float] = Field(default=None, ge=0)
    commission_l3_fixed: Optional[float] = Field(default=None, ge=0)
    commission_mode: Optional[Literal["percent", "fixed", "both"]] = None
    grace_period_days: Optional[int] = Field(default=None, ge=0, le=90)
    activity_sessions_required: Optional[int] = Field(default=None, ge=1, le=30)


# ---------- Activity Sessions ---------------------------------------------


class SessionLogCreate(BaseModel):
    program_id: Optional[str] = None  # defaults to Inner Peace
    source: Literal["manual", "module_complete", "live_session"] = "manual"
    module_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=200)


# ---------- Reports -------------------------------------------------------


ReportType = Literal["referral", "income", "downline", "subscription", "transaction"]


# ---------- View helpers --------------------------------------------------


class ActivityMeter(BaseModel):
    model_config = ConfigDict(extra="allow")
    cycle_start: Optional[str] = None
    cycle_end: Optional[str] = None
    completed: int = 0
    required: int = 4
    remaining: int = 4
    status: Literal["green", "yellow", "red", "no_plan", "no_subscription"] = "no_plan"
    subscription_id: Optional[str] = None
    program_id: Optional[str] = None
    days_left: Optional[int] = None
