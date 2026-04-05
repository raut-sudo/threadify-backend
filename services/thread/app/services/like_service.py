"""Like service — business logic for liking and unliking threads and comments.

Enforces the "one like per user" rule at the service level via
``has_user_liked_*`` checks before delegating to the repo.  The repo's
unique constraint is the final DB-level guard for concurrent requests.

Returns ``LikeResponse`` directly — a simple DTO that carries the
updated count and whether the user now likes the entity.

Every public function receives an ``AsyncSession`` and raises a domain
``AppException`` on failure.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AlreadyLikedError,
    CommentNotFoundError,
    NotLikedError,
    ThreadNotFoundError,
)
from app.repositories import comment_repo, like_repo, thread_repo
from app.schemas.like import LikeResponse

logger = logging.getLogger(__name__)


# ── Thread likes ──────────────────────────────────────────────────────────────


async def like_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> LikeResponse:
    """Like a thread. Raises ``AlreadyLikedError`` on duplicate."""
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None:
        raise ThreadNotFoundError()

    if await like_repo.has_user_liked_thread(db, user_id=user_id, thread_id=thread_id):
        raise AlreadyLikedError()

    await like_repo.like_thread(db, user_id=user_id, thread_id=thread_id)

    # Reload the count incremented atomically by the repo.
    await db.refresh(thread, attribute_names=["like_count"])
    logger.info(
        "Thread liked: thread=%s user=%s new_count=%s",
        thread_id,
        user_id,
        thread.like_count,
    )
    return LikeResponse(like_count=thread.like_count, liked=True)


async def unlike_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> LikeResponse:
    """Unlike a thread. Raises ``NotLikedError`` if not currently liked."""
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None:
        raise ThreadNotFoundError()

    if not await like_repo.has_user_liked_thread(
        db, user_id=user_id, thread_id=thread_id
    ):
        raise NotLikedError()

    await like_repo.unlike_thread(db, user_id=user_id, thread_id=thread_id)

    await db.refresh(thread, attribute_names=["like_count"])
    logger.info(
        "Thread unliked: thread=%s user=%s new_count=%s",
        thread_id,
        user_id,
        thread.like_count,
    )
    return LikeResponse(like_count=thread.like_count, liked=False)


# ── Comment likes ─────────────────────────────────────────────────────────────


async def like_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> LikeResponse:
    """Like a comment. Raises ``AlreadyLikedError`` on duplicate."""
    comment = await comment_repo.get_comment_by_id(db, comment_id)
    if comment is None:
        raise CommentNotFoundError()

    if await like_repo.has_user_liked_comment(
        db, user_id=user_id, comment_id=comment_id
    ):
        raise AlreadyLikedError()

    await like_repo.like_comment(db, user_id=user_id, comment_id=comment_id)

    await db.refresh(comment, attribute_names=["like_count"])
    logger.info(
        "Comment liked: comment=%s user=%s new_count=%s",
        comment_id,
        user_id,
        comment.like_count,
    )
    return LikeResponse(like_count=comment.like_count, liked=True)


async def unlike_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> LikeResponse:
    """Unlike a comment. Raises ``NotLikedError`` if not currently liked."""
    comment = await comment_repo.get_comment_by_id(db, comment_id)
    if comment is None:
        raise CommentNotFoundError()

    if not await like_repo.has_user_liked_comment(
        db, user_id=user_id, comment_id=comment_id
    ):
        raise NotLikedError()

    await like_repo.unlike_comment(db, user_id=user_id, comment_id=comment_id)

    await db.refresh(comment, attribute_names=["like_count"])
    logger.info(
        "Comment unliked: comment=%s user=%s new_count=%s",
        comment_id,
        user_id,
        comment.like_count,
    )
    return LikeResponse(like_count=comment.like_count, liked=False)
