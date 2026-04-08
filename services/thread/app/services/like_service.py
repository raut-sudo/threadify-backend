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
from app.events import publisher
from app.events.payloads import build_comment_like_updated, build_like_updated
from app.repositories import comment_repo, like_repo, thread_repo
from app.schemas.like import LikeResponse
from app.utils.constants import STATUS_ACTIVE

logger = logging.getLogger(__name__)


# ── Thread likes ──────────────────────────────────────────────────────────────


async def like_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> LikeResponse:
    """Like a thread. Raises ``AlreadyLikedError`` on duplicate.

    Only ACTIVE threads can be liked. Deleted threads return 404.
    """
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None:
        raise ThreadNotFoundError()
    if thread.status.name != STATUS_ACTIVE:
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
    await publisher.publish_realtime(
        "realtime.like",
        build_like_updated(
            thread_id=thread_id,
            like_count=thread.like_count,
            liked_by=user_id,
            liked=True,
        ),
    )
    return LikeResponse(like_count=thread.like_count, liked=True)


async def unlike_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
) -> LikeResponse:
    """Unlike a thread. Raises ``NotLikedError`` if not currently liked.

    Only ACTIVE threads can be unliked. Deleted threads return 404.
    """
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None:
        raise ThreadNotFoundError()
    if thread.status.name != STATUS_ACTIVE:
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
    await publisher.publish_realtime(
        "realtime.like",
        build_like_updated(
            thread_id=thread_id,
            like_count=thread.like_count,
            liked_by=user_id,
            liked=False,
        ),
    )
    return LikeResponse(like_count=thread.like_count, liked=False)


# ── Comment likes ─────────────────────────────────────────────────────────────


async def like_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> LikeResponse:
    """Like a comment. Raises ``AlreadyLikedError`` on duplicate.

    Only ACTIVE comments can be liked. Deleted comments return 404.
    """
    comment = await comment_repo.get_comment_by_id(db, comment_id)
    if comment is None:
        raise CommentNotFoundError()
    if comment.status.name != STATUS_ACTIVE:
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
    await publisher.publish_realtime(
        "realtime.comment.liked",
        build_comment_like_updated(
            thread_id=comment.thread_id,
            comment_id=comment_id,
            like_count=comment.like_count,
            liked_by=user_id,
            liked=True,
        ),
    )
    return LikeResponse(like_count=comment.like_count, liked=True)


async def unlike_comment(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> LikeResponse:
    """Unlike a comment. Raises ``NotLikedError`` if not currently liked.

    Only ACTIVE comments can be unliked. Deleted comments return 404.
    """
    comment = await comment_repo.get_comment_by_id(db, comment_id)
    if comment is None:
        raise CommentNotFoundError()
    if comment.status.name != STATUS_ACTIVE:
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
    await publisher.publish_realtime(
        "realtime.comment.liked",
        build_comment_like_updated(
            thread_id=comment.thread_id,
            comment_id=comment_id,
            like_count=comment.like_count,
            liked_by=user_id,
            liked=False,
        ),
    )
    return LikeResponse(like_count=comment.like_count, liked=False)
