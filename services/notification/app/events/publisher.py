"""RabbitMQ publisher for the notification service.

Publishes ``RealtimeNotificationEvent`` payloads to ``realtime_exchange``
(topic, durable) after a notification has been persisted to the database.
The WS gateway consumes from this exchange to push live updates to users.

Pattern: module-level singletons declared once in ``connect()`` and reused
for every ``publish_realtime()`` call — same KISS approach used in the
thread service.
"""

import logging

import aio_pika
from pydantic import BaseModel

logger = logging.getLogger(__name__)

REALTIME_EXCHANGE = "realtime_exchange"

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect(url: str) -> None:
    """Open connection and declare ``realtime_exchange``.

    Called once during FastAPI lifespan startup.
    """
    global _connection, _channel, _exchange

    _connection = await aio_pika.connect_robust(url)
    _channel = await _connection.channel()

    _exchange = await _channel.declare_exchange(
        REALTIME_EXCHANGE,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )
    logger.info("Realtime publisher connected — exchange=%s", REALTIME_EXCHANGE)


async def close() -> None:
    """Close the publisher connection.

    Called once during FastAPI lifespan shutdown.
    """
    global _connection, _channel, _exchange

    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("Realtime publisher connection closed")

    _connection = None
    _channel = None
    _exchange = None


async def publish_realtime(routing_key: str, event: BaseModel) -> None:
    """Publish *event* to ``realtime_exchange`` fire-and-forget.

    Silently skips if the exchange is not initialised (e.g. RabbitMQ
    unavailable at startup) so that the consumer loop never crashes due
    to a publish failure.
    """
    if _exchange is None:
        logger.warning(
            "Realtime exchange not initialised — dropping event routing_key=%s",
            routing_key,
        )
        return

    try:
        body = event.model_dump_json().encode()
        await _exchange.publish(
            aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=routing_key,
        )
        logger.debug("Published realtime event routing_key=%s", routing_key)
    except Exception:
        logger.exception(
            "Failed to publish realtime event routing_key=%s", routing_key
        )
