"""Repository layer for Notification database operations.

Pure data-access — no business logic, no HTTP concerns.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    actor_id: uuid.UUID,
    actor_username: str | None,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: dict | None = None,
) -> Notification:
    """Insert a new notification row."""
    notification = Notification(
        user_id=user_id,
        type=type,
        actor_id=actor_id,
        actor_username=actor_username,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_=metadata,
    )
    db.add(notification)
    await db.flush()
    logger.info(
        "Notification created: id=%s user=%s type=%s",
        notification.id,
        user_id,
        type,
    )
    return notification


async def list_notifications(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    cursor: datetime | None = None,
    limit: int = 20,
    is_read: bool | None = None,
) -> list[Notification]:
    """Paginated list of notifications for a user, newest first.

    Uses cursor-based pagination on ``created_at``.
    Optional ``is_read`` filter for read/unread filtering.
    """
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )

    if cursor is not None:
        stmt = stmt.where(Notification.created_at < cursor)

    if is_read is not None:
        stmt = stmt.where(Notification.is_read == is_read)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_notification_by_id(
    db: AsyncSession,
    notification_id: uuid.UUID,
) -> Notification | None:
    """Fetch a single notification by its primary key."""
    stmt = select(Notification).where(Notification.id == notification_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def mark_read(
    db: AsyncSession,
    notification: Notification,
) -> Notification:
    """Mark a single notification as read."""
    notification.is_read = True
    await db.flush()
    return notification


async def mark_all_read(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Mark all unread notifications as read for a user. Returns count updated."""
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount


async def unread_count(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """Count unread notifications for a user."""
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one()
