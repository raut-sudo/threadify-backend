"""Repository layer for Comment database operations.

Pure data-access — no business logic, no HTTP concerns.  Every function
receives an ``AsyncSession`` and returns ORM model instances or ``None``.

Cursor strategy
---------------
Top-level comments and replies both use ``created_at`` as the cursor.
Top-level comments are sorted newest-first (Reddit-style feed); replies
are sorted oldest-first (ASC) so conversations read chronologically.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.comment import Comment
from app.models.entity_status import EntityStatus

logger = logging.getLogger(__name__)


async def create_comment(
    db: AsyncSession,
    *,
    thread_id: uuid.UUID,
    author_id: uuid.UUID,
    content: str,
    status_id: uuid.UUID,
    parent_comment_id: uuid.UUID | None = None,
) -> Comment:
    """Insert a new comment row and return the persisted instance."""
    comment = Comment(
        thread_id=thread_id,
        author_id=author_id,
        content=content,
        status_id=status_id,
        parent_comment_id=parent_comment_id,
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment, attribute_names=["status"])
    logger.info(
        "Comment created: id=%s thread=%s parent=%s",
        comment.id,
        thread_id,
        parent_comment_id,
    )
    return comment


async def get_comment_by_id(
    db: AsyncSession,
    comment_id: uuid.UUID,
) -> Comment | None:
    """Fetch a comment by primary key with its status relationship loaded.

    Returns ``None`` if no comment matches the given UUID.
    """
    stmt = (
        select(Comment)
        .options(joinedload(Comment.status))
        .where(Comment.id == comment_id)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def list_top_level_comments(
    db: AsyncSession,
    *,
    thread_id: uuid.UUID,
    cursor: datetime | None = None,
    limit: int = 10,
    include_mod_removed: bool = False,
) -> list[Comment]:
    """Return cursor-paginated top-level comments for a thread, newest first.

    Top-level means ``parent_comment_id IS NULL``.

    Visibility:
      Regular users (include_mod_removed=False):
        ACTIVE + USER_DELETED (masked as [deleted] in route layer).
      Mods/admins (include_mod_removed=True):
        ACTIVE + USER_DELETED + MOD_REMOVED.
    """
    stmt = (
        select(Comment)
        .join(EntityStatus, Comment.status_id == EntityStatus.id)
        .options(joinedload(Comment.status))
        .where(
            Comment.thread_id == thread_id,
            Comment.parent_comment_id.is_(None),
        )
        .order_by(Comment.created_at.desc())
        .limit(limit)
    )

    if include_mod_removed:
        # Mods see all statuses
        stmt = stmt.where(
            EntityStatus.name.in_(["ACTIVE", "USER_DELETED", "MOD_REMOVED"])
        )
    else:
        # Regular users see ACTIVE + USER_DELETED (masked in route layer)
        stmt = stmt.where(EntityStatus.name.in_(["ACTIVE", "USER_DELETED"]))

    if cursor is not None:
        stmt = stmt.where(Comment.created_at < cursor)

    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def list_replies(
    db: AsyncSession,
    *,
    parent_comment_id: uuid.UUID,
    cursor: datetime | None = None,
    limit: int = 10,
    include_mod_removed: bool = False,
) -> list[Comment]:
    """Return cursor-paginated replies to a specific comment, oldest first.

    Replies are sorted ASC so conversations read chronologically.

    Visibility:
      Regular users: ACTIVE + USER_DELETED.
      Mods/admins (include_mod_removed=True): all statuses.
    """
    stmt = (
        select(Comment)
        .join(EntityStatus, Comment.status_id == EntityStatus.id)
        .options(joinedload(Comment.status))
        .where(
            Comment.parent_comment_id == parent_comment_id,
        )
        .order_by(Comment.created_at.asc())
        .limit(limit)
    )

    if include_mod_removed:
        stmt = stmt.where(
            EntityStatus.name.in_(["ACTIVE", "USER_DELETED", "MOD_REMOVED"])
        )
    else:
        stmt = stmt.where(EntityStatus.name.in_(["ACTIVE", "USER_DELETED"]))

    if cursor is not None:
        # For ASC pagination cursor returns rows created *after* the cursor.
        stmt = stmt.where(Comment.created_at > cursor)

    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def update_comment(
    db: AsyncSession,
    comment: Comment,
    **fields: object,
) -> Comment:
    """Apply a partial update to an existing comment.

    Only non-``None`` values in ``fields`` are written.
    """
    for key, value in fields.items():
        if value is not None:
            setattr(comment, key, value)

    await db.flush()
    logger.debug("Comment updated: id=%s fields=%s", comment.id, list(fields.keys()))
    return comment


async def soft_delete_comment(
    db: AsyncSession,
    comment: Comment,
    *,
    status_id: uuid.UUID,
) -> Comment:
    """Soft-delete a comment by updating its status and recording deleted_at."""
    comment.status_id = status_id
    comment.deleted_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(comment, attribute_names=["status"])
    logger.info("Comment soft-deleted: id=%s status_id=%s", comment.id, status_id)
    return comment


async def increment_reply_count(
    db: AsyncSession,
    parent_comment_id: uuid.UUID,
) -> None:
    """Atomically increment the denormalized reply counter on a comment by 1."""
    stmt = (
        update(Comment)
        .where(Comment.id == parent_comment_id)
        .values(reply_count=Comment.reply_count + 1)
    )
    await db.execute(stmt)


async def decrement_reply_count(
    db: AsyncSession,
    parent_comment_id: uuid.UUID,
) -> None:
    """Atomically decrement the denormalized reply counter by 1 (floor 0)."""
    stmt = (
        update(Comment)
        .where(Comment.id == parent_comment_id)
        .values(reply_count=func.greatest(0, Comment.reply_count - 1))
    )
    await db.execute(stmt)
