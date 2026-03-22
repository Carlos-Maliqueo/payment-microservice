from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentStatus
from app.models.event import EventType
from app.schemas.payment import PaymentCreate
from app.services.event_store import EventStoreService
from app.services.idempotency import idempotency_service
from app.repositories.payment_repository import PaymentRepository
from app.events.publisher import EventPublisher
from app.core.exceptions import (
    PaymentNotFoundException,
    DuplicateIdempotencyKeyException,
    InvalidPaymentStateException,
)
import structlog

logger = structlog.get_logger()


class PaymentService:
    """
    Application layer following CQRS pattern:
    - Commands: create_payment, process_payment, refund_payment, cancel_payment
    - Queries: get_payment, list_payments
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = PaymentRepository(session)
        self.event_store = EventStoreService(session)
        self.publisher = EventPublisher()

    # ─── COMMANDS ──────────────────────────────────────────────

    async def create_payment(self, data: PaymentCreate) -> Payment:
        # 1. Check idempotency cache
        cached = await idempotency_service.get_cached_response(data.idempotency_key)
        if cached:
            return await self.repository.get_by_id(UUID(cached["id"]))

        # 2. Acquire distributed lock
        lock_acquired = await idempotency_service.acquire_lock(data.idempotency_key)
        if not lock_acquired:
            raise DuplicateIdempotencyKeyException(data.idempotency_key)

        try:
            # 3. Check if key already exists in DB (edge case: lock race)
            existing = await self.repository.get_by_idempotency_key(data.idempotency_key)
            if existing:
                await idempotency_service.save_response(data.idempotency_key, {"id": str(existing.id)})
                return existing

            # 4. Create the payment record
            payment = Payment(
                idempotency_key=data.idempotency_key,
                amount=data.amount,
                currency=data.currency,
                status=PaymentStatus.PENDING,
                payment_method=data.payment_method,
                payer_id=data.payer_id,
                recipient_id=data.recipient_id,
                description=data.description,
                extra_data=data.extra_data or {},
            )
            self.session.add(payment)
            await self.session.flush()

            # 5. Append initiation event to event store
            await self.event_store.append_event(
                payment_id=payment.id,
                event_type=EventType.PAYMENT_INITIATED,
                payload={
                    "amount": str(data.amount),
                    "currency": data.currency,
                    "payer_id": data.payer_id,
                    "recipient_id": data.recipient_id,
                    "payment_method": data.payment_method.value,
                },
            )

            # 6. Commit transaction
            await self.session.commit()

            # 7. Publish event to RabbitMQ for async processing
            await self.publisher.publish_payment_initiated(payment)

            # 8. Cache response for idempotency
            await idempotency_service.save_response(data.idempotency_key, {"id": str(payment.id)})

            logger.info("payment_created", payment_id=str(payment.id), amount=str(data.amount))
            return payment

        except Exception as e:
            await self.session.rollback()
            await idempotency_service.release_lock(data.idempotency_key)
            logger.error("payment_creation_failed", error=str(e))
            raise

    async def process_payment(self, payment_id: UUID) -> Payment:
        """Transition payment from PENDING → PROCESSING → COMPLETED/FAILED"""
        payment = await self._get_or_raise(payment_id)

        if payment.status != PaymentStatus.PENDING:
            raise InvalidPaymentStateException(str(payment_id), payment.status, "PENDING")

        # Transition to PROCESSING
        payment.status = PaymentStatus.PROCESSING
        await self.event_store.append_event(
            payment_id=payment.id,
            event_type=EventType.PAYMENT_PROCESSING,
            payload={"processor": "internal"},
        )
        await self.session.commit()

        # Simulate payment gateway call (in real life: Stripe, Adyen, etc.)
        try:
            success = await self._call_payment_gateway(payment)
            if success:
                payment.status = PaymentStatus.COMPLETED
                payment.completed_at = datetime.now(timezone.utc)
                event_type = EventType.PAYMENT_COMPLETED
                payload = {"gateway_response": "approved"}
            else:
                payment.status = PaymentStatus.FAILED
                event_type = EventType.PAYMENT_FAILED
                payload = {"reason": "Gateway declined"}

            await self.event_store.append_event(
                payment_id=payment.id,
                event_type=event_type,
                payload=payload,
            )
            await self.session.commit()
            await self.publisher.publish_payment_status_changed(payment)
            return payment

        except Exception as e:
            payment.status = PaymentStatus.FAILED
            await self.event_store.append_event(
                payment_id=payment.id,
                event_type=EventType.PAYMENT_FAILED,
                payload={"reason": str(e)},
            )
            await self.session.commit()
            raise

    async def refund_payment(self, payment_id: UUID, reason: str, amount: Optional[Decimal] = None) -> Payment:
        payment = await self._get_or_raise(payment_id)

        if payment.status != PaymentStatus.COMPLETED:
            raise InvalidPaymentStateException(str(payment_id), payment.status, "COMPLETED")

        refund_amount = amount or payment.amount
        payment.status = PaymentStatus.REFUNDED

        await self.event_store.append_event(
            payment_id=payment.id,
            event_type=EventType.PAYMENT_REFUNDED,
            payload={"reason": reason, "refund_amount": str(refund_amount)},
        )
        await self.session.commit()
        await self.publisher.publish_payment_refunded(payment, str(refund_amount))
        logger.info("payment_refunded", payment_id=str(payment_id), amount=str(refund_amount))
        return payment

    async def cancel_payment(self, payment_id: UUID) -> Payment:
        payment = await self._get_or_raise(payment_id)

        if payment.status not in [PaymentStatus.PENDING]:
            raise InvalidPaymentStateException(str(payment_id), payment.status, "PENDING")

        payment.status = PaymentStatus.CANCELLED
        await self.event_store.append_event(
            payment_id=payment.id,
            event_type=EventType.PAYMENT_CANCELLED,
            payload={},
        )
        await self.session.commit()
        return payment

    # ─── QUERIES ───────────────────────────────────────────────

    async def get_payment(self, payment_id: UUID) -> Payment:
        return await self._get_or_raise(payment_id)

    async def list_payments(
        self,
        payer_id: Optional[str] = None,
        status: Optional[PaymentStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Payment], int]:
        return await self.repository.list_payments(payer_id, status, page, page_size)

    async def get_payment_history(self, payment_id: UUID) -> dict:
        await self._get_or_raise(payment_id)
        return await self.event_store.replay_payment_state(payment_id)

    # ─── PRIVATE ───────────────────────────────────────────────

    async def _get_or_raise(self, payment_id: UUID) -> Payment:
        payment = await self.repository.get_by_id(payment_id)
        if not payment:
            raise PaymentNotFoundException(str(payment_id))
        return payment

    async def _call_payment_gateway(self, payment: Payment) -> bool:
        """
        Simulates a payment gateway call.
        In production: integrate Stripe, PayPal, Adyen, etc.
        """
        import asyncio
        await asyncio.sleep(0.1)  # Simulate network latency
        # 90% success rate simulation
        import random
        return random.random() > 0.1