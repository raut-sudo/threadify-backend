"""RabbitMQ consumer for the WS gateway.

Connects to ``realtime_exchange`` (topic, durable) and binds a single
queue ``threadify.realtime`` with routing key ``realtime.*``.

Dispatch table (by routing key)
--------------------------------
realtime.like          → handle_like_update  → emit "like_update"  to thread room
realtime.comment       → handle_new_comment  → emit "new_comment"  to thread room
realtime.post          → handle_new_post     → emit "new_post"     to all (broadcast)
realtime.notification  → handle_notification → emit "notification" to user room

All handlers are fire-and-forget from the socket.io perspective — if no
client is in the target room the emit is a no-op (correct behaviour).
"""

import json
import logging

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.config import get_settings
from app.core.socket_manager import sio

logger = logging.getLogger(__name__)

settings = get_settings()

EXCHANGE_NAME = "realtime_exchange"
QUEUE_NAME = "threadify.realtime"
ROUTING_KEY = "realtime.*"


# ── Handlers ──────────────────────────────────────────────────────────────────


async def handle_like_update(payload: dict) -> None:
    """Broadcast a like/unlike event to all viewers of the thread."""
    thread_id = payload.get("thread_id")
    if not thread_id:
        logger.warning("handle_like_update: missing thread_id in payload")
        return

    await sio.emit(
        "like_update",
        payload.get("data", {}),
        room=f"thread:{thread_id}",
    )
    logger.debug("Emitted like_update to thread:%s", thread_id)


async def handle_new_comment(payload: dict) -> None:
    """Broadcast a new comment to all viewers of the thread."""
    thread_id = payload.get("thread_id")
    if not thread_id:
        logger.warning("handle_new_comment: missing thread_id in payload")
        return

    await sio.emit(
        "new_comment",
        payload.get("data", {}),
        room=f"thread:{thread_id}",
    )
    logger.debug("Emitted new_comment to thread:%s", thread_id)


async def handle_new_post(payload: dict) -> None:
    """Broadcast a new thread to ALL connected clients."""
    await sio.emit("new_post", payload.get("data", {}))
    logger.debug("Broadcast new_post to all clients")


async def handle_notification(payload: dict) -> None:
    """Deliver a notification to the specific user's room."""
    user_id = payload.get("user_id")
    if not user_id:
        logger.warning("handle_notification: missing user_id in payload")
        return

    await sio.emit(
        "notification",
        payload.get("data", {}),
        room=f"user:{user_id}",
    )
    logger.debug("Emitted notification to user:%s", user_id)


# ── Routing ───────────────────────────────────────────────────────────────────

_HANDLERS = {
    "realtime.like": handle_like_update,
    "realtime.comment": handle_new_comment,
    "realtime.post": handle_new_post,
    "realtime.notification": handle_notification,
}


async def _handle_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        routing_key = message.routing_key or ""
        handler = _HANDLERS.get(routing_key)

        if handler is None:
            logger.warning("No handler for routing_key=%s — dropping", routing_key)
            return

        try:
            payload = json.loads(message.body)
            await handler(payload)
        except Exception:
            logger.exception(
                "Failed to handle message routing_key=%s body=%s",
                routing_key,
                message.body[:200],
            )


# ── Consumer loop ─────────────────────────────────────────────────────────────


async def start_consumer() -> None:
    """Long-running consumer loop — wraps in ``asyncio.create_task()`` in main.

    Connects to RabbitMQ, declares the exchange + queue, and processes
    incoming messages until cancelled.
    """
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=20)

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange, routing_key=ROUTING_KEY)

    logger.info(
        "Realtime consumer ready — queue=%s exchange=%s routing_key=%s",
        QUEUE_NAME,
        EXCHANGE_NAME,
        ROUTING_KEY,
    )

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            await _handle_message(message)
