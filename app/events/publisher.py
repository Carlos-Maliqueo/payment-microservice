import json
import aio_pika
from datetime import datetime
from app.core.config import settings
from app.models.payment import Payment
import structlog

logger = structlog.get_logger()


class EventPublisher:
    """
    Publishes domain events to RabbitMQ.
    Consumers (other microservices) can subscribe to these events
    for notifications, analytics, fraud detection, etc.
    """

    async def _get_channel(self):
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            settings.PAYMENT_EXCHANGE,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        return connection, channel, exchange

    async def _publish(self, routing_key: str, payload: dict) -> None:
        connection, channel, exchange = await self._get_channel()
        try:
            message = aio_pika.Message(
                body=json.dumps(payload, default=str).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
                timestamp=datetime.utcnow(),
            )
            await exchange.publish(message, routing_key=routing_key)
            logger.info("event_published", routing_key=routing_key, payload=payload)
        finally:
            await connection.close()

    async def publish_payment_initiated(self, payment: Payment) -> None:
        await self._publish(
            routing_key="payment.initiated",
            payload={
                "event": "PAYMENT_INITIATED",
                "payment_id": str(payment.id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "payer_id": payment.payer_id,
                "recipient_id": payment.recipient_id,
                "created_at": payment.created_at.isoformat(),
            },
        )

    async def publish_payment_status_changed(self, payment: Payment) -> None:
        await self._publish(
            routing_key=f"payment.{payment.status.lower()}",
            payload={
                "event": f"PAYMENT_{payment.status}",
                "payment_id": str(payment.id),
                "status": payment.status,
                "updated_at": payment.updated_at.isoformat(),
            },
        )

    async def publish_payment_refunded(self, payment: Payment, refund_amount: str) -> None:
        await self._publish(
            routing_key="payment.refunded",
            payload={
                "event": "PAYMENT_REFUNDED",
                "payment_id": str(payment.id),
                "refund_amount": refund_amount,
                "currency": payment.currency,
            },
        )