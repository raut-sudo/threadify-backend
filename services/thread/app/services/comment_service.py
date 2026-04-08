"""Comment service — business logic for comment and reply lifecycle.

Orchestrates comment_repo + thread_repo calls, enforces authorization,
and maintains the denormalized counters:
  - ``thread.comment_count``   incremented on every new comment
  - ``comment.reply_count``    incremented when a reply is added

Deletion visibility rules:
  USER_DELETED → content masked as ``[deleted]`` in route layer;
                 children visible; counters NOT decremented (still visible).
  MOD_REMOVED  → hidden from regular users; visible to mods/admins.
                 Counters decremented (comment disappears from view).

Every public function receives an ``AsyncSession`` and raises a domain
``AppException`` on failure.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CommentNotFoundError,
    NotAuthorizedError,
    ThreadNotFoundError,
)
from app.events import publisher
from app.events.payloads import (
    build_comment_broadcast,
    build_comment_created,
    build_comment_deleted,
    build_comment_updated,
    build_mention_notification,
)
from app.repositories import comment_repo, thread_repo, user_snap_repo
from app.repositories.seed import get_cached_status_id, get_entity_status_by_name
from app.schemas.common import CursorPaginationMeta
from app.utils.constants import (
    DEFAULT_CURSOR_LIMIT,
    ROLE_ADMIN,
    ROLE_MODERATOR,
    STATUS_ACTIVE,
    STATUS_MOD_REMOVED,
    STATUS_USER_DELETED,
)
from app.utils.mentions import extract_mentions

logger = logging.getLogger(__name__)


# ── Private helpers ───────────────────────────────────────────────────────────


def _is_privileged(role: str) -> bool:
    return role in (ROLE_ADMIN, ROLE_MODERATOR)


def _build_cursor_meta(items: list, limit: int) -> CursorPaginationMeta:
    has_more = len(items) == limit
    next_cursor = items[-1].created_at.isoformat() if has_more and items else None
    return CursorPaginationMeta(next_cursor=next_cursor, has_more=has_more)


async def _require_status_id(db: AsyncSession, name: str) -> uuid.UUID:
    """Cache-first lookup, falls back to DB if cache is empty."""
    cached = get_cached_status_id(name)
    if cached is not None:
        return cached
    status = await get_entity_status_by_name(db, name)
    if status is None:
        raise RuntimeError(f"Required entity status '{name}' not found in DB.")
    return status.id


# ── Public service functions ──────────────────────────────────────────────────


async def create_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    content: str,
    parent_comment_id: uuid.UUID | None = None,
) -> object:
    """Create a new comment or reply, updating all denormalized counters.

    Validates:
    - The target thread exists and is not MOD_REMOVED.
    - If a parent is given, the parent comment exists and is not MOD_REMOVED.

    After creation:
    - ``thread.comment_count`` is incremented.
    - ``parent.reply_count`` is incremented (if this is a reply).
    """
    # Verify the thread exists and is ACTIVE — cannot comment on deleted threads
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None or thread.status.name != STATUS_ACTIVE:
        raise ThreadNotFoundError()

    # Verify parent comment if this is a reply — cannot reply to deleted comments
    if parent_comment_id is not None:
        parent = await comment_repo.get_comment_by_id(db, parent_comment_id)
        if parent is None or parent.status.name != STATUS_ACTIVE:
            raise CommentNotFoundError()

    status_id = await _require_status_id(db, STATUS_ACTIVE)
    comment = await comment_repo.create_comment(
        db,
        thread_id=thread_id,
        author_id=user_id,
        content=content,
        status_id=status_id,
        parent_comment_id=parent_comment_id,
    )

    # Maintain denormalized counters
    await thread_repo.increment_comment_count(db, thread_id)
    if parent_comment_id is not None:
        await comment_repo.increment_reply_count(db, parent_comment_id)

    logger.info(
        "Comment created: id=%s thread=%s parent=%s",
        comment.id,
        thread_id,
        parent_comment_id,
    )

    # Resolve actor_username from the denormalized user_snap cache
    snap = await user_snap_repo.get_user_snap(db, user_id)
    actor_username = snap.username if snap else None

    event = build_comment_created(
        actor_id=user_id,
        actor_username=actor_username,
        post_owner_id=thread.author_id,
        post_id=thread_id,
        comment_id=comment.id,
    )
    if event:
        await publisher.publish("notification.comment.created", event)

    await publisher.publish_realtime(
        "realtime.comment",
        build_comment_broadcast(
            comment_id=comment.id,
            thread_id=thread_id,
            parent_comment_id=parent_comment_id,
            author_id=user_id,
            author_username=actor_username,
            author_avatar_url=snap.avatar_url if snap else None,
            content=content,
            created_at=comment.created_at,
        ),
    )

    # @mention notifications
    mentioned = extract_mentions(content)
    if mentioned:
        resolved = await user_snap_repo.get_user_ids_by_usernames(
            db,
            mentioned,
        )
        if resolved:
            mention_event = build_mention_notification(
                actor_id=user_id,
                actor_username=actor_username,
                target_user_ids=list(resolved.values()),
                entity_type="COMMENT",
                entity_id=comment.id,
                thread_id=thread_id,
                content_preview=content,
            )
            if mention_event:
                await publisher.publish(
                    "notification.mentioned",
                    mention_event,
                )

    return comment


async def update_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    comment_id: uuid.UUID,
    content: str | None = None,
) -> object:
    """Update a comment's content. Only the author may update.

    Raises ``NotAuthorizedError`` if the requesting user is not the author.
    """
    comment = await comment_repo.get_comment_by_id(db, comment_id)
    if comment is None:
        raise CommentNotFoundError()

    if comment.author_id != user_id:
        raise NotAuthorizedError()

    updated = await comment_repo.update_comment(
        db,
        comment,
        content=content,
    )

    await publisher.publish_realtime(
        "realtime.comment.updated",
        build_comment_updated(
            comment_id=updated.id,
            thread_id=updated.thread_id,
            content=updated.content,
            updated_at=datetime.now(UTC),
        ),
    )

    return updated


async def delete_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    role: str,
    comment_id: uuid.UUID,
) -> object:
    """Soft-delete a comment with the appropriate status.

    - Author     → USER_DELETED  (content masked; children still visible)
    - Mod/Admin  → MOD_REMOVED   (comment and children hidden entirely)
    - Anyone else → NotAuthorizedError
    """
    comment = await comment_repo.get_comment_by_id(db, comment_id)
    if comment is None:
        raise CommentNotFoundError()

    if _is_privileged(role):
        status_name = STATUS_MOD_REMOVED
    elif comment.author_id == user_id:
        status_name = STATUS_USER_DELETED
    else:
        raise NotAuthorizedError()

    status_id = await _require_status_id(db, status_name)
    result = await comment_repo.soft_delete_comment(
        db,
        comment,
        status_id=status_id,
    )

    # Only decrement counters for MOD_REMOVED — the comment disappears from
    # all listings.  USER_DELETED comments remain visible (with masked content),
    # so counters must stay unchanged.
    if status_name == STATUS_MOD_REMOVED:
        await thread_repo.decrement_comment_count(db, comment.thread_id)
        if comment.parent_comment_id is not None:
            await comment_repo.decrement_reply_count(
                db,
                comment.parent_comment_id,
            )

    await publisher.publish_realtime(
        "realtime.comment.deleted",
        build_comment_deleted(
            comment_id=comment.id,
            thread_id=comment.thread_id,
            status=status_name,
        ),
    )

    logger.info(
        "Comment deleted: id=%s status=%s thread=%s",
        comment_id,
        status_name,
        comment.thread_id,
    )
    return result


async def get_comments_for_thread(
    db: AsyncSession,
    *,
    thread_id: uuid.UUID,
    cursor: datetime | None = None,
    limit: int = DEFAULT_CURSOR_LIMIT,
    role: str | None = None,
) -> tuple[list, CursorPaginationMeta]:
    """Return top-level comments for a thread, newest first.

    Regular users see ACTIVE + USER_DELETED (masked as [deleted]).
    Mods/admins also see MOD_REMOVED comments (for auditing).
    """
    limit = min(limit, 100)
    include_mod_removed = _is_privileged(role or "")
    comments = await comment_repo.list_top_level_comments(
        db,
        thread_id=thread_id,
        cursor=cursor,
        limit=limit,
        include_mod_removed=include_mod_removed,
    )
    meta = _build_cursor_meta(comments, limit)
    return comments, meta


async def get_replies(
    db: AsyncSession,
    *,
    parent_comment_id: uuid.UUID,
    cursor: datetime | None = None,
    limit: int = DEFAULT_CURSOR_LIMIT,
    role: str | None = None,
) -> tuple[list, CursorPaginationMeta]:
    """Return replies to a comment, oldest first (chronological order).

    Raises ``CommentNotFoundError`` if the parent does not exist.
    Regular users see ACTIVE + USER_DELETED.  Mods also see MOD_REMOVED.
    """
    parent = await comment_repo.get_comment_by_id(db, parent_comment_id)
    if parent is None:
        raise CommentNotFoundError()

    limit = min(limit, 100)
    include_mod_removed = _is_privileged(role or "")
    replies = await comment_repo.list_replies(
        db,
        parent_comment_id=parent_comment_id,
        cursor=cursor,
        limit=limit,
        include_mod_removed=include_mod_removed,
    )
    meta = _build_cursor_meta(replies, limit)
    return replies, meta
