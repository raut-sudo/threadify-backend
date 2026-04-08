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


class MentionedEvent(BaseModel):
    """Sent when a user is @mentioned in a thread or comment."""

    event_type: str  # "MENTIONED"
    actor_id: str
    actor_username: str | None
    target_user_ids: list[str]
    entity: dict  # { type: "THREAD" | "COMMENT", id }
    metadata: dict  # { thread_id, content_preview }


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


class CommentLikeUpdatedEvent(BaseModel):
    """Broadcast to all viewers of a thread when a comment like count changes."""

    event: str = "comment_like_update"
    thread_id: str
    data: dict  # { thread_id, comment_id, like_count, liked_by, liked }


class ThreadUpdatedEvent(BaseModel):
    """Broadcast when a thread's title/content/tags are edited."""

    event: str = "thread_updated"
    thread_id: str
    data: dict  # { thread_id, title, content, tags, updated_at }


class ThreadDeletedEvent(BaseModel):
    """Broadcast when a thread is soft-deleted."""

    event: str = "thread_deleted"
    thread_id: str
    data: dict  # { thread_id, status }


class CommentUpdatedEvent(BaseModel):
    """Broadcast when a comment's content is edited."""

    event: str = "comment_updated"
    thread_id: str
    data: dict  # { comment_id, thread_id, content, updated_at }


class CommentDeletedEvent(BaseModel):
    """Broadcast when a comment is soft-deleted."""

    event: str = "comment_deleted"
    thread_id: str
    data: dict  # { comment_id, thread_id, status }


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
    author_avatar_url: str | None = None,
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
            "author_avatar_url": author_avatar_url,
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
    author_avatar_url: str | None = None,
    created_at: datetime,
) -> ThreadCreatedEvent:
    """Build a ThreadCreatedEvent for global realtime broadcast."""
    return ThreadCreatedEvent(
        data={
            "id": str(thread_id),
            "title": title,
            "author_id": str(author_id),
            "author_username": author_username,
            "author_avatar_url": author_avatar_url,
            "created_at": created_at.isoformat(),
        },
    )


def build_comment_like_updated(
    *,
    thread_id: UUID,
    comment_id: UUID,
    like_count: int,
    liked_by: UUID,
    liked: bool,
) -> CommentLikeUpdatedEvent:
    """Build a CommentLikeUpdatedEvent for realtime broadcast to thread viewers."""
    tid = str(thread_id)
    return CommentLikeUpdatedEvent(
        thread_id=tid,
        data={
            "thread_id": tid,
            "comment_id": str(comment_id),
            "like_count": like_count,
            "liked_by": str(liked_by),
            "liked": liked,
        },
    )


# ── mention builder ───────────────────────────────────────────────────────────


def build_mention_notification(
    *,
    actor_id: UUID,
    actor_username: str | None,
    target_user_ids: list[UUID],
    entity_type: str,
    entity_id: UUID,
    thread_id: UUID,
    content_preview: str,
) -> MentionedEvent | None:
    """Build a MentionedEvent for users @mentioned in content.

    Filters out the actor from the target list (no self-mention).
    Returns None if no valid targets remain.
    """
    filtered = [uid for uid in target_user_ids if uid != actor_id]
    if not filtered:
        return None
    return MentionedEvent(
        event_type="MENTIONED",
        actor_id=str(actor_id),
        actor_username=actor_username,
        target_user_ids=[str(uid) for uid in filtered],
        entity={"type": entity_type, "id": str(entity_id)},
        metadata={
            "thread_id": str(thread_id),
            "content_preview": content_preview[:120],
        },
    )


# ── thread edit/delete builders ───────────────────────────────────────────────


def build_thread_updated(
    *,
    thread_id: UUID,
    title: str,
    content: str,
    tags: list[str],
    updated_at: datetime,
) -> ThreadUpdatedEvent:
    """Build a ThreadUpdatedEvent for realtime broadcast."""
    tid = str(thread_id)
    return ThreadUpdatedEvent(
        thread_id=tid,
        data={
            "thread_id": tid,
            "title": title,
            "content": content,
            "tags": tags,
            "updated_at": updated_at.isoformat(),
        },
    )


def build_thread_deleted(
    *,
    thread_id: UUID,
    status: str,
) -> ThreadDeletedEvent:
    """Build a ThreadDeletedEvent for realtime broadcast."""
    tid = str(thread_id)
    return ThreadDeletedEvent(
        thread_id=tid,
        data={"thread_id": tid, "status": status},
    )


# ── comment edit/delete builders ──────────────────────────────────────────────


def build_comment_updated(
    *,
    comment_id: UUID,
    thread_id: UUID,
    content: str,
    updated_at: datetime,
) -> CommentUpdatedEvent:
    """Build a CommentUpdatedEvent for realtime broadcast."""
    return CommentUpdatedEvent(
        thread_id=str(thread_id),
        data={
            "comment_id": str(comment_id),
            "thread_id": str(thread_id),
            "content": content,
            "updated_at": updated_at.isoformat(),
        },
    )


def build_comment_deleted(
    *,
    comment_id: UUID,
    thread_id: UUID,
    status: str,
) -> CommentDeletedEvent:
    """Build a CommentDeletedEvent for realtime broadcast."""
    return CommentDeletedEvent(
        thread_id=str(thread_id),
        data={
            "comment_id": str(comment_id),
            "thread_id": str(thread_id),
            "status": status,
        },
    )
