"""Add-on Phase 4 schemas (kept alongside existing phase2 ones)."""
from typing import Optional

from pydantic import BaseModel, Field


class PurchaseIntentCreate(BaseModel):
    """User-initiated purchase (metadata only — no payment). Used by the
    frontend once a payment SDK confirms success. In Phase 4 we accept it
    unconditionally to unlock program access; Phase 5 will bind it to
    Razorpay signature verification."""

    program_id: str
    price_paid: float = Field(default=0, ge=0)
    discount: float = Field(default=0, ge=0)
    gst_amount: float = Field(default=0, ge=0)
    total: float = Field(default=0, ge=0)


class ModuleCompleteRequest(BaseModel):
    time_spent_sec: int = Field(default=0, ge=0)


class ProgramLevelUpdate(BaseModel):
    level: Optional[int] = Field(default=None, ge=0)
