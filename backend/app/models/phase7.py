"""Phase 7 — Admin Panel & CMS schemas."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- User management ----------------------------------------------


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    state: Optional[str] = Field(default=None, min_length=2, max_length=60)
    city: Optional[str] = Field(default=None, min_length=2, max_length=60)


class AdminUserStatusUpdate(BaseModel):
    status: Literal["active", "suspended", "deactivated"]
    reason: Optional[str] = Field(default=None, max_length=300)


class AdminResetUserPassword(BaseModel):
    new_password: str = Field(min_length=8, max_length=72)


# ---------- CMS -----------------------------------------------------------


CMS_SLUGS = {
    "about": "About Us",
    "privacy": "Privacy Policy",
    "terms": "Terms of Service",
    "refund": "Refund Policy",
    "contact": "Contact Us",
    "faq": "Help & FAQ",
    "support": "Support",
    "data-security": "Data & Security",
}


class CMSPageUpsert(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    body: str = Field(max_length=200_000)
    meta_description: Optional[str] = Field(default=None, max_length=300)
    is_published: bool = True


# ---------- Banner --------------------------------------------------------


class BannerUpsert(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    image_url: str = Field(min_length=1, max_length=1000)
    cta_label: Optional[str] = Field(default=None, max_length=40)
    cta_link: Optional[str] = Field(default=None, max_length=500)
    placement: Literal["home", "programs", "offer", "festival", "announcement"] = "home"
    priority: int = Field(default=0, ge=0, le=1000)
    schedule_start: Optional[str] = None  # ISO
    schedule_end: Optional[str] = None
    is_active: bool = True


# ---------- Notifications (admin compose) --------------------------------


class NotificationSend(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    category: Literal[
        "announcement",
        "offer",
        "renewal",
        "program",
        "activity",
        "system",
    ] = "announcement"
    # Targeting
    is_broadcast: bool = True  # if true, delivered to all users
    target_membership_ids: Optional[list[str]] = None  # if set, target list
    cta_link: Optional[str] = None


# ---------- System / Security settings -----------------------------------


class SystemSettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    company_logo_url: Optional[str] = None
    company_address: Optional[str] = None
    company_gst_number: Optional[str] = None
    support_email: Optional[str] = None
    support_mobile: Optional[str] = None
    website: Optional[str] = None
    social_facebook: Optional[str] = None
    social_instagram: Optional[str] = None
    social_youtube: Optional[str] = None
    social_linkedin: Optional[str] = None
    social_twitter: Optional[str] = None
    application_version: Optional[str] = None
    maintenance_mode: Optional[bool] = None


class SecuritySettingsUpdate(BaseModel):
    password_min_length: Optional[int] = Field(default=None, ge=6, le=64)
    otp_expiry_seconds: Optional[int] = Field(default=None, ge=60, le=1800)
    login_attempt_limit: Optional[int] = Field(default=None, ge=3, le=20)
    session_timeout_minutes: Optional[int] = Field(default=None, ge=5, le=1440)


# ---------- Views --------------------------------------------------------


class DashboardOverview(BaseModel):
    model_config = ConfigDict(extra="allow")
    total_users: int
    active_users: int
    inactive_users: int
    todays_registrations: int
    total_programs: int
    total_purchases: int
    active_subscribers: int
    expired_subscribers: int
    pending_payout_amount: float
    paid_payout_amount: float
    pending_program_expiry: int
    revenue_today: float
    revenue_month: float
    revenue_year: float
