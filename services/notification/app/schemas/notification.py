"""Pydantic schemas for notification request / response models."""

import uuid
from datetime import datetime  # noqa: I001

from pydantic import BaseModel, Field

# ── Pagination ────────────────────────────────────────────────────────────────


class CursorPaginationMeta(BaseModel):
    next_cursor: str | None = None
    has_more: bool


# ── Response models ───────────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    actor_id: uuid.UUID
    actor_username: str | None
    entity_type: str
    entity_id: uuid.UUID
    metadata: dict | None = Field(None, validation_alias="metadata_")
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    meta: CursorPaginationMeta


class UnreadCountResponse(BaseModel):
    count: int


class MessageResponse(BaseModel):
    message: str
