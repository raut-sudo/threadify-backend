"""Pydantic schemas for user snapshot endpoints.

UserSnap is the denormalized author display data embedded inside
thread and comment responses.  It is also exposed via temporary
CRUD endpoints (``api/v1/user_snaps.py``) for local testing until
the event-driven pipeline is in place.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserSnapResponse(BaseModel):
    """Public author display data embedded in thread / comment responses.

    Uses ``from_attributes`` so it can be built directly from the
    ``UserSnap`` ORM instance without an explicit mapping step.
    """

    user_id: uuid.UUID
    username: str
    avatar_url: str | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSnapCreate(BaseModel):
    """Payload for creating or upserting a user snapshot.

    Sent by the temporary testing endpoint (``POST /user-snaps``).
    In production this data arrives via an inter-service event.
    """

    user_id: uuid.UUID
    username: str = Field(min_length=1, max_length=50)
    avatar_url: str | None = None


class UserSnapUpdate(BaseModel):
    """Partial-update payload for ``PATCH /user-snaps/{user_id}``.

    Every field is optional — only the fields the client sends
    will be applied.
    """

    username: str | None = Field(default=None, min_length=1, max_length=50)
    avatar_url: str | None = None
