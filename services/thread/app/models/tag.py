"""Tag ORM model and thread_tags association table.

Tags use a many-to-many relationship with threads via the ``thread_tags``
join table.  Tag names are stored **lowercase** and have a unique
constraint to avoid duplicates.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# ── Association table (no ORM class needed) ───────────────────────────────────

thread_tags = Table(
    "thread_tags",
    Base.metadata,
    Column(
        "thread_id",
        UUID(as_uuid=True),
        ForeignKey("threads.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ── Tag model ─────────────────────────────────────────────────────────────────


class Tag(Base):
    """A tag that can be attached to one or more threads.

    ``name`` is stored lowercase and must be unique.
    """

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<Tag name={self.name!r}>"
