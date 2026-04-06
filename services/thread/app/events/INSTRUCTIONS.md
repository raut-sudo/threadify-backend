I want to create a events from the thread service when anyone comments on the post of a user and then emit this event as a producer to the rabbit mq , WRITE MINIMAL CODE that to within the events folder


- the event on where someone comments on a user's post, the user must be notified , so a payload is to be sent , send user_id, username of the commentator and uid of the owner of the post  

- this event (payload) will later be consumed by the thread service 


- try to do it with minimal files and simple code following standard, clean code practices 


This a demo reference STRICTLY FOR REFERENCE , 

publisher.py :
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import aio_pika
from aio_pika import ExchangeType, DeliveryMode, Message

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "notification_exchange"

# Held for the lifetime of the process
_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_exchange: aio_pika.abc.AbstractExchange | None = None


async def connect(url: str) -> None:
    global _connection, _channel, _exchange
    _connection = await aio_pika.connect_robust(url)
    _channel = await _connection.channel()
    _exchange = await _channel.declare_exchange(
        EXCHANGE_NAME,
        ExchangeType.TOPIC,
        durable=True,
    )
    logger.info("RabbitMQ connected, exchange '%s' ready", EXCHANGE_NAME)


async def close() -> None:
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("RabbitMQ connection closed")


async def publish(routing_key: str, payload: dict[str, Any]) -> None:
    """
    Publish a single event. Silently logs on failure so a RabbitMQ outage
    never breaks the HTTP response — per the spec rule 'emit AFTER DB success'.
    """
    if _exchange is None:
        logger.warning("RabbitMQ not connected; dropping event %s", routing_key)
        return

    payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    try:
        await _exchange.publish(
            Message(
                body=json.dumps(payload, default=str).encode(),
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
    except Exception:
        logger.exception("Failed to publish event '%s'", routing_key)


2. payloads.py 
"""
Builders for every event type defined in content_events.txt.
Each function returns (routing_key, payload).
All return None for target_user_ids entries equal to actor_id (no self-notification).
"""
from typing import Any, Optional
from uuid import UUID


def _dedup(actor_id: UUID, *user_ids: UUID | None) -> list[str]:
    """Return unique target ids, excluding the actor and None values."""
    seen: set[UUID] = {actor_id}
    result: list[str] = []
    for uid in user_ids:
        if uid and uid not in seen:
            seen.add(uid)
            result.append(str(uid))
    return result


# ---------------------------------------------------------------------------
# Post like / unlike
# ---------------------------------------------------------------------------

def post_liked(
    actor_id: UUID,
    post_id: UUID,
    post_owner_id: UUID,
    actor_username: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    return (
        "notification.post.liked",
        {
            "event_type": "POST_LIKED",
            "actor_id": str(actor_id),
            "actor_username": actor_username,
            "target_user_ids": _dedup(actor_id, post_owner_id),
            "entity": {"type": "POST", "id": str(post_id)},
        },
    )


def post_unliked(
    actor_id: UUID,
    post_id: UUID,
    post_owner_id: UUID,
    actor_username: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    return (
        "notification.post.disliked",
        {
            "event_type": "POST_UNLIKED",
            "actor_id": str(actor_id),
            "actor_username": actor_username,
            "target_user_ids": _dedup(actor_id, post_owner_id),
            "entity": {"type": "POST", "id": str(post_id)},
        },
    )


# ---------------------------------------------------------------------------
# Comment like / unlike
# ---------------------------------------------------------------------------

def comment_liked(
    actor_id: UUID,
    comment_id: UUID,
    comment_owner_id: UUID,
    post_id: UUID,
    actor_username: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    return (
        "notification.comment.liked",
        {
            "event_type": "COMMENT_LIKED",
            "actor_id": str(actor_id),
            "actor_username": actor_username,
            "target_user_ids": _dedup(actor_id, comment_owner_id),
            "entity": {"type": "COMMENT", "id": str(comment_id)},
            "metadata": {"post_id": str(post_id)},
        },
    )


def comment_unliked(
    actor_id: UUID,
    comment_id: UUID,
    comment_owner_id: UUID,
    post_id: UUID,
    actor_username: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    return (
        "notification.comment.disliked",
        {
            "event_type": "COMMENT_UNLIKED",
            "actor_id": str(actor_id),
            "actor_username": actor_username,
            "target_user_ids": _dedup(actor_id, comment_owner_id),
            "entity": {"type": "COMMENT", "id": str(comment_id)},
            "metadata": {"post_id": str(post_id)},
        },
    )


# ---------------------------------------------------------------------------
# Comment created (top-level)
# ---------------------------------------------------------------------------

def comment_created(
    actor_id: UUID,
    post_id: UUID,
    post_owner_id: UUID,
    comment_id: UUID,
    actor_username: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    return (
        "notification.comment.created",
        {
            "event_type": "COMMENT_CREATED",
            "actor_id": str(actor_id),
            "actor_username": actor_username,
            "target_user_ids": _dedup(actor_id, post_owner_id),
            "entity": {"type": "POST", "id": str(post_id)},
            "metadata": {"comment_id": str(comment_id)},
        },
    )


# ---------------------------------------------------------------------------
# Reply to comment
# ---------------------------------------------------------------------------

def comment_replied(
    actor_id: UUID,
    post_id: UUID,
    post_owner_id: UUID,
    parent_comment_id: UUID,
    parent_comment_owner_id: UUID,
    reply_id: UUID,
    actor_username: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    return (
        "notification.comment.replied",
        {
            "event_type": "COMMENT_REPLIED",
            "actor_id": str(actor_id),
            "actor_username": actor_username,
            "target_user_ids": _dedup(actor_id, post_owner_id, parent_comment_owner_id),
            "entity": {"type": "COMMENT", "id": str(parent_comment_id)},
            "metadata": {
                "reply_comment_id": str(reply_id),
                "post_id": str(post_id),
                "post_owner_id": str(post_owner_id),
                "parent_comment_owner_id": str(parent_comment_owner_id),
            },
        },
    )


# ---------------------------------------------------------------------------
# Content deleted by moderator
# ---------------------------------------------------------------------------

def content_deleted(
    moderator_id: UUID,
    owner_id: UUID,
    entity_type: str,  # "POST" or "COMMENT"
    entity_id: UUID,
    reason: str | None = None,
    actor_username: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "event_type": "CONTENT_DELETED",
        "actor_id": str(moderator_id),
        "actor_username": actor_username,
        "target_user_ids": _dedup(moderator_id, owner_id),
        "entity": {"type": entity_type, "id": str(entity_id)},
    }
    if reason:
        payload["metadata"] = {"reason": reason}
    return "notification.content.deleted", payload


# ---------------------------------------------------------------------------
# User role changed (promotion / demotion)
# ---------------------------------------------------------------------------

def user_role_changed(
    moderator_id: UUID,
    affected_user_id: UUID,
    old_role: str,
    new_role: str,
    actor_username: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    return (
        "notification.user.role_changed",
        {
            "event_type": "USER_ROLE_CHANGED",
            "actor_id": str(moderator_id),
            "actor_username": actor_username,
            "target_user_ids": _dedup(moderator_id, affected_user_id),
            "entity": {"type": "USER", "id": str(affected_user_id)},
            "metadata": {"old_role": old_role, "new_role": new_role},
        },
    )


