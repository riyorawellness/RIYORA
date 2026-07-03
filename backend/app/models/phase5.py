"""Phase 5 — Razorpay Payment Engine schemas.

All amounts on the API surface are in **rupees** (float). Razorpay uses paise
internally; conversion is done inside the payment service, not exposed here.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Orders (Standard Checkout / one-time) --------------------------


class CreateOrderRequest(BaseModel):
    """User initiates a purchase — server creates a Razorpay order.

    `program_id` is required; server recomputes final amount (price - discount + GST)
    from the program row and current admin settings. Client-supplied amount is
    ignored to prevent tampering.
    """

    program_id: str


class CreateOrderResponse(BaseModel):
    order_id: str  # rzp order id (or mock_ord_xxx)
    amount_paise: int  # amount in paise
    amount_rupees: float
    currency: str = "INR"
    receipt: str
    key_id: str  # razorpay key id for frontend checkout script
    is_mock: bool
    program: dict
    breakdown: dict  # {price, discount, taxable, gst_percent, gst_amount, total}
    prefill: dict  # {name, contact}
    notes: dict = Field(default_factory=dict)


class VerifyPaymentRequest(BaseModel):
    """Sent by frontend after Razorpay Checkout resolves successfully.

    In mock-mode the values are provided by the frontend mock modal.
    Server verifies HMAC(order_id + '|' + payment_id, key_secret) == signature.
    """

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    success: bool
    purchase_id: str
    invoice_number: str
    expiry_date: str
    amount: float
    program_id: str


# ---------- Subscription (mock only in this phase) -------------------------


class CreateSubscriptionRequest(BaseModel):
    program_id: str
    plan: Literal["monthly", "yearly"] = "monthly"


class CreateSubscriptionResponse(BaseModel):
    subscription_id: str
    status: str
    plan: str
    next_charge_at: Optional[str] = None
    program: dict
    is_mock: bool


# ---------- Webhook --------------------------------------------------------


class WebhookAck(BaseModel):
    status: str = "processed"


# ---------- Admin ----------------------------------------------------------


class RefundRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class PaymentSettingsUpdate(BaseModel):
    default_gst_percent: Optional[float] = Field(default=None, ge=0, le=100)
    default_validity_days: Optional[int] = Field(default=None, gt=0)
    company_gst_number: Optional[str] = Field(default=None, max_length=32)
    invoice_prefix: Optional[str] = Field(default=None, max_length=8)


# ---------- Read helpers ---------------------------------------------------


class PaymentOrderView(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    order_id: str
    user_membership_id: str
    program_id: str
    amount_paise: int
    status: str
