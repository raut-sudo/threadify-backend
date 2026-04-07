"""RabbitMQ consumer — background task that persists incoming events.

Runs as an ``asyncio.Task`` created during the FastAPI lifespan.
Connects to the ``notification_exchange`` (topic, durable) and binds
a durable queue ``threadify.notifications`` with routing key ``notification.*``.

Each incoming message is parsed and fanned out into one ``Notification``
row per ``target_user_id`` in the event payload.
"""

import json
import logging
import uuid

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repositories import notification_repo
from app.events import publisher as realtime_publisher
from app.events.payloads import build_realtime_notification

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "notification_exchange"
QUEUE_NAME = "threadify.notifications"
ROUTING_KEY = "notification.*"


async def consume(
    rabbitmq_url: str,
    session_factory: async_sessionmaker,
) -> None:
    """Long-running consumer loop.

    Connects to RabbitMQ, declares the queue + binding, and processes
    messages forever.  Designed to be wrapped in ``asyncio.create_task()``.
    """
    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange, routing_key=ROUTING_KEY)

    logger.info(
        "Consumer ready — queue=%s, exchange=%s, routing_key=%s",
        QUEUE_NAME,
        EXCHANGE_NAME,
        ROUTING_KEY,
    )

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            await _handle_message(message, session_factory)


async def _handle_message(
    message: AbstractIncomingMessage,
    session_factory: async_sessionmaker,
) -> None:
    """Process a single message — insert one notification per target user."""
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body)
            logger.info(
                "Event received: type=%s routing_key=%s",
                payload.get("event_type"),
                message.routing_key,
            )

            target_user_ids = payload.get("target_user_ids", [])
            if not target_user_ids:
                logger.warning("Event has no target_user_ids — skipping")
                return

            entity = payload.get("entity", {})

            notifications = []
            async with session_factory() as db:
                for uid_str in target_user_ids:
                    notification = await notification_repo.create_notification(
                        db,
                        user_id=uuid.UUID(uid_str),
                        type=payload["event_type"],
                        actor_id=uuid.UUID(payload["actor_id"]),
                        actor_username=payload.get("actor_username"),
                        entity_type=entity.get("type", "UNKNOWN"),
                        entity_id=uuid.UUID(entity["id"]),
                        metadata=payload.get("metadata"),
                    )
                    notifications.append(notification)
                await db.commit()

            # Publish realtime event for each notification
            for notification in notifications:
                await realtime_publisher.publish_realtime(
                    "realtime.notification",
                    build_realtime_notification(notification),
                )

            logger.info(
                "Persisted %d notification(s) for event_type=%s",
                len(target_user_ids),
                payload["event_type"],
            )

        except Exception:
            logger.exception("Failed to process message: %s", message.body[:200])
