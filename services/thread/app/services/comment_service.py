"""Comment service — business logic for comment and reply lifecycle.

Orchestrates comment_repo + thread_repo calls, enforces authorization,
and maintains the denormalized counters:
  - ``thread.comment_count``   incremented on every new comment
  - ``comment.reply_count``    incremented when a reply is added

Deletion visibility rules mirror those for threads (§9 LLD):
  USER_DELETED → content masked as ``[deleted]`` in route layer; children visible
  MOD_REMOVED  → hidden; children hidden; excluded from all listings

Every public function receives an ``AsyncSession`` and raises a domain
``AppException`` on failure.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CommentNotFoundError,
    NotAuthorizedError,
    ThreadNotFoundError,
)
from app.repositories import comment_repo, thread_repo
from app.repositories.seed import get_entity_status_by_name
from app.schemas.common import CursorPaginationMeta
from app.utils.constants import (
    DEFAULT_CURSOR_LIMIT,
    ROLE_ADMIN,
    ROLE_MODERATOR,
    STATUS_ACTIVE,
    STATUS_MOD_REMOVED,
    STATUS_USER_DELETED,
)

logger = logging.getLogger(__name__)


# ── Private helpers ───────────────────────────────────────────────────────────


def _is_privileged(role: str) -> bool:
    return role in (ROLE_ADMIN, ROLE_MODERATOR)


def _build_cursor_meta(items: list, limit: int) -> CursorPaginationMeta:
    has_more = len(items) == limit
    next_cursor = items[-1].created_at.isoformat() if has_more and items else None
    return CursorPaginationMeta(next_cursor=next_cursor, has_more=has_more)


async def _require_status_id(db: AsyncSession, name: str) -> uuid.UUID:
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
    # Verify the thread is accessible
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None or thread.status.name == STATUS_MOD_REMOVED:
        raise ThreadNotFoundError()

    # Verify parent comment if this is a reply
    if parent_comment_id is not None:
        parent = await comment_repo.get_comment_by_id(db, parent_comment_id)
        if parent is None or parent.status.name == STATUS_MOD_REMOVED:
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

    return await comment_repo.update_comment(db, comment, content=content)


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
    return await comment_repo.soft_delete_comment(db, comment, status_id=status_id)


async def get_comments_for_thread(
    db: AsyncSession,
    *,
    thread_id: uuid.UUID,
    cursor: datetime | None = None,
    limit: int = DEFAULT_CURSOR_LIMIT,
) -> tuple[list, CursorPaginationMeta]:
    """Return top-level comments for a thread, newest first.

    MOD_REMOVED comments are excluded by the repository layer.
    USER_DELETED comments are included — route handler applies masking.
    """
    limit = min(limit, 100)
    comments = await comment_repo.list_top_level_comments(
        db, thread_id=thread_id, cursor=cursor, limit=limit
    )
    meta = _build_cursor_meta(comments, limit)
    return comments, meta


async def get_replies(
    db: AsyncSession,
    *,
    parent_comment_id: uuid.UUID,
    cursor: datetime | None = None,
    limit: int = DEFAULT_CURSOR_LIMIT,
) -> tuple[list, CursorPaginationMeta]:
    """Return replies to a comment, oldest first (chronological order).

    Raises ``CommentNotFoundError`` if the parent does not exist.
    MOD_REMOVED replies are excluded by the repository layer.
    """
    parent = await comment_repo.get_comment_by_id(db, parent_comment_id)
    if parent is None:
        raise CommentNotFoundError()

    limit = min(limit, 100)
    replies = await comment_repo.list_replies(
        db, parent_comment_id=parent_comment_id, cursor=cursor, limit=limit
    )
    meta = _build_cursor_meta(replies, limit)
    return replies, meta
