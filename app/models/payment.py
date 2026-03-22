import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Numeric, DateTime, Enum, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class PaymentStatus(str, PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, PyEnum):
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    CRYPTO = "CRYPTO"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    payer_id = Column(String(255), nullable=False, index=True)
    recipient_id = Column(String(255), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    extra_data = Column(JSON, nullable=True, default=dict)
    retry_count = Column(String(10), nullable=False, default="0")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    events = relationship("PaymentEvent", back_populates="payment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_payments_status_created", "status", "created_at"),
        Index("ix_payments_payer_status", "payer_id", "status"),
    )

    def __repr__(self):
        return f"<Payment id={self.id} status={self.status} amount={self.amount} {self.currency}>"