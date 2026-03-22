from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.db.session import get_session
from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    PaymentListResponse,
    RefundRequest,
)
from app.services.payment_service import PaymentService
from app.models.payment import PaymentStatus

router = APIRouter(prefix="/payments", tags=["Payments"])


def get_payment_service(session: AsyncSession = Depends(get_session)) -> PaymentService:
    return PaymentService(session)


@router.post("/", response_model=PaymentResponse, status_code=201)
async def create_payment(
    data: PaymentCreate,
    service: PaymentService = Depends(get_payment_service),
):
    """
    Create a new payment.

    - **idempotency_key**: Unique key to prevent duplicate payments (required)
    - **amount**: Payment amount in the specified currency
    - **currency**: ISO 4217 currency code (e.g., USD, EUR)
    - **payment_method**: Method of payment
    - Sending the same idempotency_key twice returns the original response (safe retry)
    """
    payment = await service.create_payment(data)
    return payment


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    service: PaymentService = Depends(get_payment_service),
):
    """Get payment details by ID."""
    return await service.get_payment(payment_id)


@router.get("/", response_model=PaymentListResponse)
async def list_payments(
    payer_id: Optional[str] = Query(None),
    status: Optional[PaymentStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: PaymentService = Depends(get_payment_service),
):
    """List payments with optional filters."""
    items, total = await service.list_payments(payer_id, status, page, page_size)
    return PaymentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{payment_id}/process", response_model=PaymentResponse)
async def process_payment(
    payment_id: UUID,
    service: PaymentService = Depends(get_payment_service),
):
    """Trigger payment processing (PENDING → PROCESSING → COMPLETED/FAILED)."""
    return await service.process_payment(payment_id)


@router.post("/{payment_id}/refund", response_model=PaymentResponse)
async def refund_payment(
    payment_id: UUID,
    data: RefundRequest,
    service: PaymentService = Depends(get_payment_service),
):
    """Refund a completed payment (full or partial)."""
    return await service.refund_payment(payment_id, data.reason, data.amount)


@router.post("/{payment_id}/cancel", response_model=PaymentResponse)
async def cancel_payment(
    payment_id: UUID,
    service: PaymentService = Depends(get_payment_service),
):
    """Cancel a pending payment."""
    return await service.cancel_payment(payment_id)


@router.get("/{payment_id}/history")
async def get_payment_history(
    payment_id: UUID,
    service: PaymentService = Depends(get_payment_service),
):
    """
    Get the complete event history for a payment.
    Returns all events in sequence — the Event Sourcing audit trail.
    """
    return await service.get_payment_history(payment_id)