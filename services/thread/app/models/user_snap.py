"""UserSnap ORM model — denormalized user display data.

Stores a minimal copy of user profile fields needed for rendering
thread/comment author information without making a cross-service
call on every read.

The ``user_id`` is the PK (same value as the user service's user ID) —
there is no surrogate key here.  Snapshots are populated and kept
up-to-date via event-driven inter-service messages (Kafka/RabbitMQ).
Temporary CRUD endpoints are exposed in ``api/v1/user_snaps.py`` for
local testing until the event pipeline is in place.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserSnap(Base):
    """A cached snapshot of a user's public profile.

    Fields intentionally minimal — only what is needed for display
    next to a thread or comment.  Do not add sensitive user data here.
    """

    __tablename__ = "user_snap"

    # user_id IS the PK — mirrors the user service's user.id.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<UserSnap user_id={self.user_id} username={self.username!r}>"
