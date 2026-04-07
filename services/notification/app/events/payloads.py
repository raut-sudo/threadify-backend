"""Realtime event payload schemas for the notification service.

Published to ``realtime_exchange`` after a notification is persisted,
so the WS gateway can push it to the correct user's socket immediately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.models.notification import Notification


class RealtimeNotificationEvent(BaseModel):
    """Payload sent to ``realtime_exchange`` with routing key ``realtime.notification``.

    ``user_id`` lets the WS gateway route the event to the recipient's socket.
    ``data`` mirrors the REST notification shape.
    """

    event: str = "notification"
    user_id: str  # recipient — WS gateway uses this to target the right room
    data: dict[str, Any]


def build_realtime_notification(notification: "Notification") -> RealtimeNotificationEvent:
    """Build a ``RealtimeNotificationEvent`` from a persisted ``Notification`` ORM row."""
    return RealtimeNotificationEvent(
        user_id=str(notification.user_id),
        data={
            "id": str(notification.id),
            "type": notification.type,
            "actor_id": str(notification.actor_id),
            "actor_username": notification.actor_username,
            "entity_type": notification.entity_type,
            "entity_id": str(notification.entity_id),
            "metadata": notification.metadata_,
            "is_read": notification.is_read,
            "created_at": notification.created_at.isoformat(),
        },
    )
