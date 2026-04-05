"""Repository layer for Thread and Comment like operations.

Pure data-access — no business logic, no HTTP concerns.  Every function
receives an ``AsyncSession`` and returns ORM instances or scalar values.

Like / unlike atomicity
-----------------------
Like and unlike operations perform two steps inside the same DB session:
  1. Insert / delete the like row.
  2. Atomically increment / decrement the denormalized ``like_count``
     on the parent thread or comment using a SQL ``UPDATE ... SET count + 1``.

Both steps are flushed together before the session commits, so the
counter and the like record are always consistent.

The unique constraint on ``(user_id, thread_id)`` / ``(user_id, comment_id)``
in the DB acts as a final guard against concurrent double-likes, but the
service layer checks via ``has_user_liked_*`` first to give a clean error.
"""

import logging
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.models.comment_like import CommentLike
from app.models.thread import Thread
from app.models.thread_like import ThreadLike

logger = logging.getLogger(__name__)


# ── Thread likes ──────────────────────────────────────────────────────────────


async def has_user_liked_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> bool:
    """Return ``True`` if the user has already liked this thread."""
    stmt = select(ThreadLike).where(
        ThreadLike.user_id == user_id,
        ThreadLike.thread_id == thread_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def like_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> ThreadLike:
    """Insert a thread like row and atomically increment the like counter.

    Caller must verify the user has not already liked this thread
    via ``has_user_liked_thread`` before calling to surface a clean error.
    """
    like = ThreadLike(user_id=user_id, thread_id=thread_id)
    db.add(like)

    await db.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(like_count=Thread.like_count + 1)
    )
    await db.flush()
    logger.info("Thread liked: thread=%s user=%s", thread_id, user_id)
    return like


async def unlike_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> None:
    """Delete a thread like row and atomically decrement the like counter.

    Caller must verify the like exists via ``has_user_liked_thread``
    before calling to surface a clean error.
    """
    await db.execute(
        delete(ThreadLike).where(
            ThreadLike.user_id == user_id,
            ThreadLike.thread_id == thread_id,
        )
    )
    await db.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(like_count=Thread.like_count - 1)
    )
    await db.flush()
    logger.info("Thread unliked: thread=%s user=%s", thread_id, user_id)


# ── Comment likes ─────────────────────────────────────────────────────────────


async def has_user_liked_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> bool:
    """Return ``True`` if the user has already liked this comment."""
    stmt = select(CommentLike).where(
        CommentLike.user_id == user_id,
        CommentLike.comment_id == comment_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def like_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> CommentLike:
    """Insert a comment like row and atomically increment the like counter.

    Caller must verify the user has not already liked this comment.
    """
    like = CommentLike(user_id=user_id, comment_id=comment_id)
    db.add(like)

    await db.execute(
        update(Comment)
        .where(Comment.id == comment_id)
        .values(like_count=Comment.like_count + 1)
    )
    await db.flush()
    logger.info("Comment liked: comment=%s user=%s", comment_id, user_id)
    return like


async def unlike_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> None:
    """Delete a comment like row and atomically decrement the like counter.

    Caller must verify the like exists via ``has_user_liked_comment``.
    """
    await db.execute(
        delete(CommentLike).where(
            CommentLike.user_id == user_id,
            CommentLike.comment_id == comment_id,
        )
    )
    await db.execute(
        update(Comment)
        .where(Comment.id == comment_id)
        .values(like_count=Comment.like_count - 1)
    )
    await db.flush()
    logger.info("Comment unliked: comment=%s user=%s", comment_id, user_id)
