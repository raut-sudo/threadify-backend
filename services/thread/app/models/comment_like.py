"""CommentLike ORM model — per-user like record for comments.

Mirrors ``ThreadLike`` in structure.  A composite unique constraint on
(user_id, comment_id) enforces the "like once" invariant at the
database level.

``like_count`` on the ``comments`` table is the denormalized aggregate;
this table is the source of truth for individual user likes.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CommentLike(Base):
    """Records that a specific user has liked a specific comment."""

    __tablename__ = "comment_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "comment_id", name="uq_comment_like_user_comment"),
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
    comment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<CommentLike user={self.user_id} comment={self.comment_id}>"
