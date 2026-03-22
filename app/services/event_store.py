from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.event import PaymentEvent, EventType
from uuid import UUID
import structlog

logger = structlog.get_logger()


class EventStoreService:
    """
    Append-only event store. Every state change in the payment lifecycle
    is recorded as an immutable event. This enables:
    - Full audit trail
    - Event replay for debugging
    - Temporal queries (what was the state at time T?)
    - Event-driven projections
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def append_event(
        self,
        payment_id: UUID,
        event_type: str,
        payload: dict,
        metadata: dict = None,
        created_by: str = "system",
    ) -> PaymentEvent:
        # Get next sequence number for this payment
        result = await self.session.execute(
            select(func.count(PaymentEvent.id)).where(
                PaymentEvent.payment_id == payment_id
            )
        )
        sequence_number = (result.scalar() or 0) + 1

        event = PaymentEvent(
            payment_id=payment_id,
            event_type=event_type,
            sequence_number=sequence_number,
            payload=payload,
            metadata=metadata or {},
            created_by=created_by,
        )
        self.session.add(event)
        await self.session.flush()

        logger.info(
            "event_appended",
            payment_id=str(payment_id),
            event_type=event_type,
            sequence=sequence_number,
        )
        return event

    async def get_events(self, payment_id: UUID) -> List[PaymentEvent]:
        """Retrieve all events for a payment in order."""
        result = await self.session.execute(
            select(PaymentEvent)
            .where(PaymentEvent.payment_id == payment_id)
            .order_by(PaymentEvent.sequence_number)
        )
        return result.scalars().all()

    async def replay_payment_state(self, payment_id: UUID) -> dict:
        """
        Reconstruct payment state by replaying all events.
        This is the core concept of Event Sourcing.
        """
        events = await self.get_events(payment_id)
        state = {"payment_id": str(payment_id), "status": None, "history": []}

        for event in events:
            state["history"].append({
                "sequence": event.sequence_number,
                "event_type": event.event_type,
                "payload": event.payload,
                "timestamp": event.created_at.isoformat(),
            })
            # Apply state transition based on event type
            if event.event_type == EventType.PAYMENT_INITIATED:
                state["status"] = "PENDING"
                state.update(event.payload)
            elif event.event_type == EventType.PAYMENT_PROCESSING:
                state["status"] = "PROCESSING"
            elif event.event_type == EventType.PAYMENT_COMPLETED:
                state["status"] = "COMPLETED"
                state["completed_at"] = event.created_at.isoformat()
            elif event.event_type == EventType.PAYMENT_FAILED:
                state["status"] = "FAILED"
                state["failure_reason"] = event.payload.get("reason")
            elif event.event_type == EventType.PAYMENT_REFUNDED:
                state["status"] = "REFUNDED"

        return state