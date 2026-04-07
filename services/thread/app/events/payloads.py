"""Event payload schemas and builder functions.

Each builder returns a typed Pydantic model (or None for suppressed events)
that the publisher serialises to JSON.

Two exchanges are used:
  notification_exchange — CommentCreatedEvent  (persistence path)
  realtime_exchange     — LikeUpdatedEvent, CommentBroadcastEvent,
                          ThreadCreatedEvent   (broadcast path)
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

# ── notification_exchange payloads ────────────────────────────────────────────


class CommentCreatedEvent(BaseModel):
    event_type: str
    actor_id: str
    actor_username: str | None
    target_user_ids: list[str]
    entity: dict
    metadata: dict


# ── realtime_exchange payloads ────────────────────────────────────────────────


class LikeUpdatedEvent(BaseModel):
    """Broadcast to all viewers of a thread when like count changes."""

    event: str = "like_update"
    thread_id: str
    data: dict  # { thread_id, like_count, liked_by, liked }


class CommentBroadcastEvent(BaseModel):
    """Broadcast to all viewers of a thread when a new comment is posted."""

    event: str = "new_comment"
    thread_id: str
    data: dict  # { id, thread_id, parent_comment_id, author_id, author_username, content, created_at }


class ThreadCreatedEvent(BaseModel):
    """Broadcast to all connected clients when a new thread is created."""

    event: str = "new_post"
    data: dict  # { id, title, author_id, author_username, created_at }


# ── notification_exchange builders ────────────────────────────────────────────


def build_comment_created(
    *,
    actor_id: UUID,
    actor_username: str | None,
    post_owner_id: UUID,
    post_id: UUID,
    comment_id: UUID,
) -> CommentCreatedEvent | None:
    """Build a CommentCreatedEvent payload.

    Returns None when actor_id == post_owner_id (self-comment suppression).
    The caller should check for None before publishing.
    """
    if actor_id == post_owner_id:
        return None

    return CommentCreatedEvent(
        event_type="COMMENT_CREATED",
        actor_id=str(actor_id),
        actor_username=actor_username,
        target_user_ids=[str(post_owner_id)],
        entity={"type": "THREAD", "id": str(post_id)},
        metadata={"comment_id": str(comment_id)},
    )


# ── realtime_exchange builders ────────────────────────────────────────────────


def build_like_updated(
    *,
    thread_id: UUID,
    like_count: int,
    liked_by: UUID,
    liked: bool,
) -> LikeUpdatedEvent:
    """Build a LikeUpdatedEvent for realtime broadcast to thread viewers."""
    tid = str(thread_id)
    return LikeUpdatedEvent(
        thread_id=tid,
        data={
            "thread_id": tid,
            "like_count": like_count,
            "liked_by": str(liked_by),
            "liked": liked,
        },
    )


def build_comment_broadcast(
    *,
    comment_id: UUID,
    thread_id: UUID,
    parent_comment_id: UUID | None,
    author_id: UUID,
    author_username: str | None,
    content: str,
    created_at: datetime,
) -> CommentBroadcastEvent:
    """Build a CommentBroadcastEvent for realtime broadcast to thread viewers."""
    return CommentBroadcastEvent(
        thread_id=str(thread_id),
        data={
            "id": str(comment_id),
            "thread_id": str(thread_id),
            "parent_comment_id": str(parent_comment_id) if parent_comment_id else None,
            "author_id": str(author_id),
            "author_username": author_username,
            "content": content,
            "created_at": created_at.isoformat(),
        },
    )


def build_thread_created(
    *,
    thread_id: UUID,
    title: str,
    author_id: UUID,
    author_username: str | None,
    created_at: datetime,
) -> ThreadCreatedEvent:
    """Build a ThreadCreatedEvent for global realtime broadcast."""
    return ThreadCreatedEvent(
        data={
            "id": str(thread_id),
            "title": title,
            "author_id": str(author_id),
            "author_username": author_username,
            "created_at": created_at.isoformat(),
        },
    )
