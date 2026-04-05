"""Thread ORM model — the primary discussion post table.

A thread is the top-level content unit. It tracks its own like count
and comment count as denormalized integers so feed queries never need
aggregation joins.

Soft-delete is modelled via ``status_id`` (referencing ``entity_status``)
and a nullable ``deleted_at`` timestamp. The actual row is never removed.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Thread(Base):
    """A discussion thread authored by a single user.

    ``author_id`` is a UUID that references the user service — no FK
    constraint is applied because users live in a separate database.
    Display data is denormalized into ``user_snap`` instead.

    ``status_id`` references ``entity_status.id`` (ACTIVE /
    USER_DELETED / MOD_REMOVED).  Use ``deleted_at`` to record when
    a soft-delete occurred for audit purposes.
    """

    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Cross-service FK — intentionally no DB-level constraint.
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    status_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entity_status.id", ondelete="RESTRICT"),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    like_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    comment_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # ── Relationships ────────────────────────────────
    # joined: status is always needed when displaying a thread — avoids N+1.
    status: Mapped["EntityStatus"] = relationship(  # noqa: F821
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Thread id={self.id} author={self.author_id}>"
