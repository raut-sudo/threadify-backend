"""Pydantic schemas for comment endpoints.

Covers request validation (create / partial update) and response
serialisation.  ``CommentResponse`` embeds a ``UserSnapResponse`` so
the author's display name and avatar are always available without a
second round-trip.

Deletion visibility rules (applied in the service layer):
  ACTIVE       → content rendered normally
  USER_DELETED → content replaced with ``"[deleted]"``; children visible
  MOD_REMOVED  → entire comment hidden from regular users
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import CursorPaginationMeta
from app.schemas.user_snap import UserSnapResponse


class CommentCreate(BaseModel):
    """Payload for ``POST /comments``.

    ``parent_comment_id`` is ``None`` for top-level comments and a
    valid comment UUID for replies.
    """

    thread_id: uuid.UUID
    parent_comment_id: uuid.UUID | None = None
    content: str = Field(min_length=1)


class CommentUpdate(BaseModel):
    """Partial-update payload for ``PATCH /comments/{id}``.

    Only content can be updated post-creation.  ``thread_id``,
    ``parent_comment_id``, and ``author_id`` are immutable.
    """

    content: str | None = Field(default=None, min_length=1)


class CommentResponse(BaseModel):
    """Full comment representation returned by GET and POST endpoints.

    ``author`` is the denormalized ``UserSnap`` for the comment author.
    ``status``  is the name string (e.g. ``"ACTIVE"``), not the UUID,
    so clients never need to resolve the status table themselves.
    ``is_liked`` indicates whether the requesting user has liked this
    comment (``False`` for unauthenticated requests).
    ``content``  may be ``"[deleted]"`` when status is ``USER_DELETED``;
    this masking is applied in the service layer before serialisation.
    """

    id: uuid.UUID
    thread_id: uuid.UUID
    parent_comment_id: uuid.UUID | None = None
    author_id: uuid.UUID
    author: UserSnapResponse | None = None
    content: str
    status: str  # EntityStatus.name — resolved in the service layer
    like_count: int
    reply_count: int
    is_liked: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentListResponse(BaseModel):
    """Paginated list of comments / replies."""

    comments: list[CommentResponse]
    pagination: CursorPaginationMeta
