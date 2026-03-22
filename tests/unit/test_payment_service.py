import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from decimal import Decimal

from app.services.payment_service import PaymentService
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.schemas.payment import PaymentCreate
from app.core.exceptions import (
    PaymentNotFoundException,
    InvalidPaymentStateException,
)

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def payment_service(mock_session):
    service = PaymentService(mock_session)
    service.repository = AsyncMock()
    service.event_store = AsyncMock()
    service.publisher = AsyncMock()
    return service


@pytest.fixture
def sample_payment():
    return Payment(
        id=uuid4(),
        idempotency_key="test-key-001",
        amount=Decimal("100.00"),
        currency="USD",
        status=PaymentStatus.PENDING,
        payment_method=PaymentMethod.CREDIT_CARD,
        payer_id="user-123",
        recipient_id="merchant-456",
    )


class TestGetPayment:
    async def test_get_existing_payment(self, payment_service, sample_payment):
        payment_service.repository.get_by_id.return_value = sample_payment
        result = await payment_service.get_payment(sample_payment.id)
        assert result.id == sample_payment.id
        assert result.status == PaymentStatus.PENDING

    async def test_get_nonexistent_payment_raises(self, payment_service):
        payment_service.repository.get_by_id.return_value = None
        with pytest.raises(PaymentNotFoundException):
            await payment_service.get_payment(uuid4())


class TestProcessPayment:
    async def test_process_pending_payment_success(self, payment_service, sample_payment):
        payment_service.repository.get_by_id.return_value = sample_payment

        with patch.object(payment_service, "_call_payment_gateway", return_value=True):
            result = await payment_service.process_payment(sample_payment.id)

        assert result.status == PaymentStatus.COMPLETED

    async def test_process_pending_payment_failure(self, payment_service, sample_payment):
        payment_service.repository.get_by_id.return_value = sample_payment

        with patch.object(payment_service, "_call_payment_gateway", return_value=False):
            result = await payment_service.process_payment(sample_payment.id)

        assert result.status == PaymentStatus.FAILED

    async def test_process_non_pending_raises(self, payment_service, sample_payment):
        sample_payment.status = PaymentStatus.COMPLETED
        payment_service.repository.get_by_id.return_value = sample_payment

        with pytest.raises(InvalidPaymentStateException):
            await payment_service.process_payment(sample_payment.id)


class TestRefundPayment:
    async def test_refund_completed_payment(self, payment_service, sample_payment):
        sample_payment.status = PaymentStatus.COMPLETED
        payment_service.repository.get_by_id.return_value = sample_payment

        result = await payment_service.refund_payment(sample_payment.id, "Customer request")
        assert result.status == PaymentStatus.REFUNDED

    async def test_refund_non_completed_raises(self, payment_service, sample_payment):
        payment_service.repository.get_by_id.return_value = sample_payment  # PENDING
        with pytest.raises(InvalidPaymentStateException):
            await payment_service.refund_payment(sample_payment.id, "reason")

    async def test_partial_refund(self, payment_service, sample_payment):
        sample_payment.status = PaymentStatus.COMPLETED
        payment_service.repository.get_by_id.return_value = sample_payment

        result = await payment_service.refund_payment(
            sample_payment.id, "Partial refund", amount=Decimal("50.00")
        )
        assert result.status == PaymentStatus.REFUNDED
        payment_service.event_store.append_event.assert_called_once()
        call_payload = payment_service.event_store.append_event.call_args.kwargs["payload"]
        assert call_payload["refund_amount"] == "50.00"


class TestCancelPayment:
    async def test_cancel_pending_payment(self, payment_service, sample_payment):
        payment_service.repository.get_by_id.return_value = sample_payment
        result = await payment_service.cancel_payment(sample_payment.id)
        assert result.status == PaymentStatus.CANCELLED

    async def test_cancel_processing_raises(self, payment_service, sample_payment):
        sample_payment.status = PaymentStatus.PROCESSING
        payment_service.repository.get_by_id.return_value = sample_payment

        with pytest.raises(InvalidPaymentStateException):
            await payment_service.cancel_payment(sample_payment.id)