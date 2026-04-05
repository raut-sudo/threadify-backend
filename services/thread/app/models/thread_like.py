"""ThreadLike ORM model — per-user like record for threads.

A composite unique constraint on (user_id, thread_id) enforces the
"like once" invariant at the database level, providing a hard
guarantee even under concurrent requests.

``like_count`` on the ``threads`` table is the denormalized aggregate;
this table is the source of truth for individual user likes.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ThreadLike(Base):
    """Records that a specific user has liked a specific thread."""

    __tablename__ = "thread_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "thread_id", name="uq_thread_like_user_thread"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Cross-service FK — intentionally no DB-level constraint.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<ThreadLike user={self.user_id} thread={self.thread_id}>"
