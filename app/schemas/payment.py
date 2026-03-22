from pydantic import BaseModel, Field, condecimal
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from app.models.payment import PaymentStatus, PaymentMethod
from decimal import Decimal


class PaymentCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=255, description="Unique key to prevent duplicate payments")
    amount: Decimal = Field(..., gt=0, le=1_000_000, description="Payment amount (max 1,000,000)")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_method: PaymentMethod
    payer_id: str = Field(..., min_length=1, max_length=255)
    recipient_id: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    extra_data: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "idempotency_key": "order-123-payment-001",
                "amount": "99.99",
                "currency": "USD",
                "payment_method": "CREDIT_CARD",
                "payer_id": "user-456",
                "recipient_id": "merchant-789",
                "description": "Purchase of product XYZ",
                "metadata": {"order_id": "order-123", "product_ids": ["prod-1"]},
            }
        }


class PaymentResponse(BaseModel):
    id: UUID
    idempotency_key: str
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_method: PaymentMethod
    payer_id: str
    recipient_id: str
    description: Optional[str]
    extra_data: Optional[Dict[str, Any]]
    retry_count: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int
    page: int
    page_size: int


class RefundRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
    amount: Optional[Decimal] = Field(None, gt=0, description="Partial refund amount. If None, full refund.")


class PaymentStatusUpdate(BaseModel):
    status: PaymentStatus
    metadata: Optional[Dict[str, Any]] = None