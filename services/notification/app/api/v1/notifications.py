"""Notification REST endpoints.

All endpoints require Bearer authentication.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.notification import (
    MessageResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services import notification_service
from app.utils.constants import DEFAULT_CURSOR_LIMIT, MAX_CURSOR_LIMIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    cursor: str | None = Query(None, description="ISO-8601 cursor from previous page"),
    limit: int = Query(DEFAULT_CURSOR_LIMIT, ge=1, le=MAX_CURSOR_LIMIT),
    is_read: bool | None = Query(None, description="Filter by read status"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Paginated list of notifications for the authenticated user."""
    return await notification_service.list_notifications(
        db,
        user_id=current_user["user_id"],
        cursor=cursor,
        limit=limit,
        is_read=is_read,
    )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark a single notification as read."""
    return await notification_service.mark_read(
        db,
        user_id=current_user["user_id"],
        notification_id=notification_id,
    )


@router.patch("/read-all", response_model=MessageResponse)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark all unread notifications as read for the authenticated user."""
    count = await notification_service.mark_all_read(
        db,
        user_id=current_user["user_id"],
    )
    return MessageResponse(message=f"Marked {count} notification(s) as read")


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return the count of unread notifications."""
    return await notification_service.get_unread_count(
        db,
        user_id=current_user["user_id"],
    )
