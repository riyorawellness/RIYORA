"""Phase 11 — Manual QR Payment System (Provider-pattern).

Data model:
    payment_settings    Company QR + UPI + bank details (single active record).
    payment_requests    User-submitted manual payment records awaiting admin verification.
    program_purchases   On approval, a row is inserted here with source='manual_qr'
                        so all downstream business logic (access, commissions,
                        certificates, reports) works unchanged.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, constr


class PaymentSettingsUpsert(BaseModel):
    """Admin-editable QR + bank settings."""
    company_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    bank_name: Optional[str] = None
    upi_id: Optional[str] = None
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    qr_image_url: Optional[str] = None
    payment_instructions: Optional[str] = None
    is_active: Optional[bool] = None


class PaymentSubmitRequest(BaseModel):
    program_id: str
    utr: constr(strip_whitespace=True, min_length=6, max_length=40)
    transaction_date: constr(pattern=r"^\d{4}-\d{2}-\d{2}$")  # ISO date YYYY-MM-DD
    screenshot_url: str    # produced by /api/admin/uploads or a new /uploads/screenshot
    remarks: Optional[str] = Field(default=None, max_length=500)


class PaymentActionRequest(BaseModel):
    action: Literal["approve", "reject"]
    remarks: Optional[str] = Field(default=None, max_length=500)
    rejection_reason: Optional[str] = Field(default=None, max_length=500)


class PaymentModeUpdate(BaseModel):
    payment_mode: Literal["manual_qr", "razorpay", "both"]


ALLOWED_MODES = ("manual_qr", "razorpay", "both")
