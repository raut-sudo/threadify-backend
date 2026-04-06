"""Notification service — thin orchestration layer.

Sits between the API / consumer layers and the repository.
Enforces ownership checks and builds response schemas.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotAuthorizedError, NotificationNotFoundError
from app.repositories import notification_repo
from app.schemas.notification import (
    CursorPaginationMeta,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.utils.constants import DEFAULT_CURSOR_LIMIT

logger = logging.getLogger(__name__)


def _build_cursor_meta(items: list, limit: int) -> CursorPaginationMeta:
    has_more = len(items) == limit
    next_cursor = items[-1].created_at.isoformat() if has_more and items else None
    return CursorPaginationMeta(next_cursor=next_cursor, has_more=has_more)


async def list_notifications(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = DEFAULT_CURSOR_LIMIT,
    is_read: bool | None = None,
) -> NotificationListResponse:
    """Paginated notifications for the authenticated user."""
    cursor_dt = datetime.fromisoformat(cursor) if cursor else None

    items = await notification_repo.list_notifications(
        db,
        user_id=user_id,
        cursor=cursor_dt,
        limit=limit,
        is_read=is_read,
    )

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        meta=_build_cursor_meta(items, limit),
    )


async def mark_read(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> NotificationResponse:
    """Mark a single notification as read. Enforces ownership."""
    notification = await notification_repo.get_notification_by_id(db, notification_id)
    if notification is None:
        raise NotificationNotFoundError()
    if notification.user_id != user_id:
        raise NotAuthorizedError()

    updated = await notification_repo.mark_read(db, notification)
    return NotificationResponse.model_validate(updated)


async def mark_all_read(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> int:
    """Mark all unread notifications as read. Returns count updated."""
    return await notification_repo.mark_all_read(db, user_id)


async def get_unread_count(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> UnreadCountResponse:
    """Return the unread notification count for the user."""
    count = await notification_repo.unread_count(db, user_id)
    return UnreadCountResponse(count=count)
