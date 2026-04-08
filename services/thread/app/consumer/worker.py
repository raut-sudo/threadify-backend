"""RabbitMQ consumer — keeps the local UserSnap cache in sync.

Runs as an ``asyncio.Task`` created during the FastAPI lifespan.
Connects to the ``user_exchange`` (topic, durable) and binds
a durable queue ``threadify.user_snaps`` with routing key ``user.*``.

Handled routing keys
--------------------
  user.registered — new user signed up; insert or upsert snap
  user.updated    — username / avatar changed; update existing snap

Each incoming message is parsed and passed to ``user_snap_repo.upsert_user_snap``
so that thread and comment responses always carry up-to-date author info.
"""

import json
import logging
import uuid

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repositories import user_snap_repo

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "user_exchange"
QUEUE_NAME = "threadify.user_snaps"
ROUTING_KEY = "user.*"


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
        "UserSnap consumer ready — queue=%s, exchange=%s, routing_key=%s",
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
    """Parse a ``user.registered`` or ``user.updated`` message and upsert the snap."""
    async with message.process(requeue=False):
        try:
            payload = json.loads(message.body)
            event_type = payload.get("event_type", "unknown")
            user_id_str = payload.get("user_id")
            username = payload.get("username")
            avatar_url = payload.get("avatar_url")

            logger.info(
                "UserSnap event received: type=%s user_id=%s",
                event_type,
                user_id_str,
            )

            if not user_id_str or not username:
                logger.warning(
                    "UserSnap event missing required fields — skipping: %s", payload
                )
                return

            async with session_factory() as db:
                await user_snap_repo.upsert_user_snap(
                    db,
                    user_id=uuid.UUID(user_id_str),
                    username=username,
                    avatar_url=avatar_url,
                )
                await db.commit()

            logger.info(
                "UserSnap upserted: user_id=%s username=%s", user_id_str, username
            )

        except Exception:
            logger.exception(
                "Failed to process UserSnap event (routing_key=%s)",
                message.routing_key,
            )
