from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.payment import Payment, PaymentStatus


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, payment_id: UUID) -> Optional[Payment]:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Optional[Payment]:
        result = await self.session.execute(
            select(Payment).where(Payment.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def list_payments(
        self,
        payer_id: Optional[str] = None,
        status: Optional[PaymentStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Payment], int]:
        query = select(Payment)
        count_query = select(func.count(Payment.id))

        if payer_id:
            query = query.where(Payment.payer_id == payer_id)
            count_query = count_query.where(Payment.payer_id == payer_id)
        if status:
            query = query.where(Payment.status == status)
            count_query = count_query.where(Payment.status == status)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar()

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        return result.scalars().all(), total