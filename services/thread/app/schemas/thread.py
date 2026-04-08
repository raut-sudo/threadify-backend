"""Pydantic schemas for thread endpoints.

Covers request validation (create / partial update) and response
serialisation.  ``ThreadResponse`` embeds a ``UserSnapResponse`` so
the author's display name and avatar are always available without a
second round-trip.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import CursorPaginationMeta
from app.schemas.user_snap import UserSnapResponse


class ThreadCreate(BaseModel):
    """Payload for ``POST /threads``."""

    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list, max_length=10)


class ThreadUpdate(BaseModel):
    """Partial-update payload for ``PATCH /threads/{id}``.

    Both fields are optional — at least one must be non-null for the
    update to be meaningful (enforced in the service layer).
    """

    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = Field(default=None, max_length=10)


class ThreadResponse(BaseModel):
    """Full thread representation returned by GET and POST endpoints.

    ``author`` is the denormalized ``UserSnap`` for the thread author.
    ``status``  is the name string (e.g. ``"ACTIVE"``), not the UUID,
    so clients never need to resolve the status table themselves.
    ``is_liked`` indicates whether the requesting user has liked this
    thread (``False`` for unauthenticated requests).
    """

    id: uuid.UUID
    title: str
    content: str
    author_id: uuid.UUID
    author: UserSnapResponse | None = None
    status: str  # EntityStatus.name — resolved in the service layer
    like_count: int
    comment_count: int
    is_liked: bool = False
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ThreadListResponse(BaseModel):
    """Paginated list of threads returned by ``GET /threads``."""

    threads: list[ThreadResponse]
    pagination: CursorPaginationMeta
