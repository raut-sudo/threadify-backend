"""RabbitMQ event publisher.

Module-level singleton pattern — one connection shared for the process lifetime.
Call connect() at startup and close() at shutdown (both wired into lifespan).

Two exchanges are declared on connect:
  notification_exchange — durable topic, consumed by notification-service
  realtime_exchange     — durable topic, consumed by ws-gateway

Both publish functions are fire-and-forget: a broker failure is logged but
never raised, so a RabbitMQ outage never breaks the HTTP response.
"""

import logging

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from pydantic import BaseModel

logger = logging.getLogger(__name__)

NOTIFICATION_EXCHANGE = "notification_exchange"
REALTIME_EXCHANGE = "realtime_exchange"

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None
_realtime_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect(url: str) -> None:
    """Open a robust connection and declare both durable topic exchanges."""
    global _connection, _channel, _exchange, _realtime_exchange
    _connection = await aio_pika.connect_robust(url)
    _channel = await _connection.channel()
    _exchange = await _channel.declare_exchange(
        NOTIFICATION_EXCHANGE,
        ExchangeType.TOPIC,
        durable=True,
    )
    _realtime_exchange = await _channel.declare_exchange(
        REALTIME_EXCHANGE,
        ExchangeType.TOPIC,
        durable=True,
    )
    logger.info(
        "RabbitMQ connected — exchanges '%s' and '%s' ready",
        NOTIFICATION_EXCHANGE,
        REALTIME_EXCHANGE,
    )


async def close() -> None:
    """Close the connection gracefully on application shutdown."""
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("RabbitMQ connection closed")


async def publish(routing_key: str, event: BaseModel) -> None:
    """Publish to notification_exchange. Fire-and-forget."""
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
        logger.info("Event published to notification_exchange: '%s'", routing_key)
    except Exception:
        logger.exception("Failed to publish event '%s'", routing_key)


async def publish_realtime(routing_key: str, event: BaseModel) -> None:
    """Publish to realtime_exchange (consumed by ws-gateway). Fire-and-forget."""
    if _realtime_exchange is None:
        logger.warning(
            "RabbitMQ not connected — dropping realtime event '%s'", routing_key
        )
        return

    try:
        await _realtime_exchange.publish(
            Message(
                body=event.model_dump_json().encode(),
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
        logger.info("Event published to realtime_exchange: '%s'", routing_key)
    except Exception:
        logger.exception("Failed to publish realtime event '%s'", routing_key)
