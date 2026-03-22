import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class PaymentEvent(Base):
    """
    Event Store table - immutable append-only log of all payment state changes.
    This is the heart of Event Sourcing pattern.
    """
    __tablename__ = "payment_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    event_version = Column(Integer, nullable=False, default=1)
    sequence_number = Column(Integer, nullable=False)  # Order within payment lifecycle
    payload = Column(JSON, nullable=False, default=dict)
    extra_data = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(255), nullable=True)  # User/service that triggered the event

    payment = relationship("Payment", back_populates="events")

    __table_args__ = (
        Index("ix_events_payment_sequence", "payment_id", "sequence_number"),
        Index("ix_events_type_created", "event_type", "created_at"),
    )

    def __repr__(self):
        return f"<PaymentEvent id={self.id} type={self.event_type} payment_id={self.payment_id}>"


# Event type constants
class EventType:
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_REFUNDED = "PAYMENT_REFUNDED"
    PAYMENT_CANCELLED = "PAYMENT_CANCELLED"
    RETRY_ATTEMPTED = "RETRY_ATTEMPTED"