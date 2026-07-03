"""Phase 2 Pydantic schemas: Programs, Modules, Purchases, Progress, Assessments,
Certificates, Referral Tree, Bank Details, Settings, Notifications, Profiles."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, EmailStr


# ---------- Common ---------------------------------------------------------
class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------- Profiles -------------------------------------------------------
class ProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    dob: Optional[str] = Field(default=None, description="ISO-8601 date (YYYY-MM-DD)")
    gender: Optional[Literal["male", "female", "other", "prefer_not"]] = None
    address: Optional[str] = Field(default=None, max_length=500)
    profile_photo_url: Optional[str] = Field(default=None, max_length=1024)
    occupation: Optional[str] = Field(default=None, max_length=100)
    alt_contact: Optional[str] = Field(default=None, max_length=20)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    user_membership_id: str
    email: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    profile_photo_url: Optional[str] = None
    occupation: Optional[str] = None
    alt_contact: Optional[str] = None


# ---------- Program Categories --------------------------------------------
class ProgramCategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    order_index: int = 0
    is_active: bool = True


class ProgramCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    order_index: Optional[int] = None
    is_active: Optional[bool] = None


# ---------- Programs -------------------------------------------------------
class ProgramCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(min_length=2, max_length=150, pattern=r"^[a-z0-9-]+$")
    short_description: Optional[str] = Field(default=None, max_length=280)
    description: Optional[str] = Field(default=None, max_length=5000)
    thumbnail_url: Optional[str] = Field(default=None, max_length=1024)
    banner_url: Optional[str] = Field(default=None, max_length=1024)
    price: float = Field(ge=0)
    discount: float = Field(default=0, ge=0)
    gst_percent: float = Field(default=18, ge=0, le=100)
    validity_days: int = Field(gt=0)
    category_id: Optional[str] = None
    order_index: int = 0
    is_active: bool = True
    is_subscription: bool = False
    level: Optional[int] = Field(default=None, ge=0, le=10)


class ProgramUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    short_description: Optional[str] = Field(default=None, max_length=280)
    description: Optional[str] = Field(default=None, max_length=5000)
    thumbnail_url: Optional[str] = Field(default=None, max_length=1024)
    banner_url: Optional[str] = Field(default=None, max_length=1024)
    price: Optional[float] = Field(default=None, ge=0)
    discount: Optional[float] = Field(default=None, ge=0)
    gst_percent: Optional[float] = Field(default=None, ge=0, le=100)
    validity_days: Optional[int] = Field(default=None, gt=0)
    category_id: Optional[str] = None
    order_index: Optional[int] = None
    is_active: Optional[bool] = None
    is_subscription: Optional[bool] = None
    level: Optional[int] = Field(default=None, ge=0, le=10)


# ---------- Program Modules -----------------------------------------------
class ProgramModuleCreate(BaseModel):
    program_id: str
    module_number: int = Field(ge=1)
    name: str = Field(min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    video_url: Optional[str] = Field(default=None, max_length=1024)
    audio_url: Optional[str] = Field(default=None, max_length=1024)
    pdf_url: Optional[str] = Field(default=None, max_length=1024)
    assignment: Optional[str] = Field(default=None, max_length=5000)
    quiz_id: Optional[str] = None
    order_index: int = 0
    sequential_unlock: bool = True
    is_active: bool = True


class ProgramModuleUpdate(BaseModel):
    module_number: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    video_url: Optional[str] = Field(default=None, max_length=1024)
    audio_url: Optional[str] = Field(default=None, max_length=1024)
    pdf_url: Optional[str] = Field(default=None, max_length=1024)
    assignment: Optional[str] = Field(default=None, max_length=5000)
    quiz_id: Optional[str] = None
    order_index: Optional[int] = None
    sequential_unlock: Optional[bool] = None
    is_active: Optional[bool] = None


# ---------- Assessments ---------------------------------------------------
class AssessmentQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int = Field(ge=0)


class AssessmentCreate(BaseModel):
    module_id: str
    program_id: str
    title: str = Field(min_length=2, max_length=150)
    questions: list[AssessmentQuestion] = Field(min_length=1)
    passing_marks: int = Field(ge=0)
    attempts_allowed: int = Field(default=3, ge=1)
    randomize: bool = False


class AssessmentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=150)
    questions: Optional[list[AssessmentQuestion]] = None
    passing_marks: Optional[int] = Field(default=None, ge=0)
    attempts_allowed: Optional[int] = Field(default=None, ge=1)
    randomize: Optional[bool] = None


class AssessmentResultCreate(BaseModel):
    assessment_id: str
    answers: list[int] = Field(min_length=1)


# ---------- Program Purchases (metadata only — no payment) ----------------
class ProgramPurchaseCreate(BaseModel):
    user_membership_id: str = Field(pattern=r"^RW\d{6}$")
    program_id: str
    price_paid: float = Field(ge=0)
    discount: float = Field(default=0, ge=0)
    gst_amount: float = Field(default=0, ge=0)
    total: float = Field(ge=0)
    invoice_number: str = Field(min_length=3, max_length=50)
    purchase_date: Optional[str] = None
    expiry_date: Optional[str] = None
    renewal_date: Optional[str] = None
    status: Literal["active", "expired", "cancelled", "pending"] = "active"


class ProgramPurchaseUpdate(BaseModel):
    expiry_date: Optional[str] = None
    renewal_date: Optional[str] = None
    status: Optional[Literal["active", "expired", "cancelled", "pending"]] = None


# ---------- Program Progress ----------------------------------------------
class ProgramProgressUpdate(BaseModel):
    completed_modules: Optional[list[str]] = None
    current_module_id: Optional[str] = None
    percentage: Optional[float] = Field(default=None, ge=0, le=100)
    completion_date: Optional[str] = None
    certificate_eligible: Optional[bool] = None


# ---------- Certificates ---------------------------------------------------
class CertificateCreate(BaseModel):
    user_membership_id: str = Field(pattern=r"^RW\d{6}$")
    program_id: str
    certificate_number: str = Field(min_length=3, max_length=60)
    issue_date: Optional[str] = None
    completion_date: Optional[str] = None
    status: Literal["issued", "revoked"] = "issued"
    pdf_url: Optional[str] = Field(default=None, max_length=1024)


class CertificateUpdate(BaseModel):
    status: Optional[Literal["issued", "revoked"]] = None
    pdf_url: Optional[str] = Field(default=None, max_length=1024)


# ---------- Bank Details --------------------------------------------------
class BankDetailsUpsert(BaseModel):
    account_holder: str = Field(min_length=2, max_length=100)
    bank_name: str = Field(min_length=2, max_length=100)
    account_number: str = Field(min_length=6, max_length=30)
    ifsc: str = Field(pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")
    upi_id: Optional[str] = Field(default=None, max_length=100)


# ---------- Settings -------------------------------------------------------
class UserSettingUpsert(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    value: Any


class AppSettingUpsert(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    value: Any
    description: Optional[str] = Field(default=None, max_length=500)


class SystemConfigurationUpsert(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    value: Any
    description: Optional[str] = Field(default=None, max_length=500)


# ---------- Notifications (DB rows only — no push) ------------------------
class NotificationCreate(BaseModel):
    user_membership_id: Optional[str] = Field(
        default=None, description="Target user; leave null for broadcast."
    )
    title: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="general", max_length=50)
    meta: dict = Field(default_factory=dict)


class NotificationMarkRead(BaseModel):
    ids: list[str] = Field(min_length=1)


# ---------- Referral Tree --------------------------------------------------
class ReferralTreeUpdate(BaseModel):
    status: Optional[Literal["active", "inactive", "suspended"]] = None
