"""RabbitMQ event publisher.

Module-level singleton pattern — one connection shared for the process lifetime.
Call connect() at startup and close() at shutdown (both wired into lifespan).

publish() is fire-and-forget: a broker failure is logged but never raised,
so a RabbitMQ outage never breaks the HTTP response.
"""

import logging

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from app.events.payloads import CommentCreatedEvent

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "notification_exchange"

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect(url: str) -> None:
    """Open a robust connection and declare the durable topic exchange."""
    global _connection, _channel, _exchange
    _connection = await aio_pika.connect_robust(url)
    _channel = await _connection.channel()
    _exchange = await _channel.declare_exchange(
        EXCHANGE_NAME,
        ExchangeType.TOPIC,
        durable=True,
    )
    logger.info("RabbitMQ connected — exchange '%s' ready", EXCHANGE_NAME)


async def close() -> None:
    """Close the connection gracefully on application shutdown."""
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("RabbitMQ connection closed")


async def publish(routing_key: str, event: CommentCreatedEvent) -> None:
    """Publish a single event. Silently logs on failure."""
    if _exchange is None:
        logger.warning("RabbitMQ not connected — dropping event '%s'", routing_key)
        return

    try:
        await _exchange.publish(
            Message(
                body=event.model_dump_json().encode(),
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
        logger.info("Event published: '%s'", routing_key)
    except Exception:
        logger.exception("Failed to publish event '%s'", routing_key)
