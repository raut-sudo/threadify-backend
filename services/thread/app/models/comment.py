"""Comment ORM model — nested reply table.

Comments form an adjacency-list tree:
  - Top-level comments have ``parent_comment_id = NULL``.
  - Replies point to their immediate parent via ``parent_comment_id``.

Nesting is unbounded in the schema.  The application enforces display
limits (lazy-load replies on demand via ``GET /comments?parent_id=``).

Like threads, comments use soft-delete: ``status_id`` records the
reason and ``deleted_at`` records when it happened.  Content for
USER_DELETED comments is rendered as ``[deleted]`` in the API layer;
MOD_REMOVED comments are hidden entirely from regular users.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Comment(Base):
    """A comment (or nested reply) on a thread.

    ``author_id`` is cross-service — no DB FK to the user table.
    ``thread_id`` cascades on thread deletion so orphan comments are
    cleaned up automatically.
    ``parent_comment_id`` is self-referential; NULL means top-level.
    """

    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # NULL → top-level comment; non-NULL → reply to another comment.
    parent_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Cross-service FK — intentionally no DB-level constraint.
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
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
    reply_count: Mapped[int] = mapped_column(
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

    # ── Relationships ────────────────────────────────

    # joined: status is always needed when displaying a comment.
    status: Mapped["EntityStatus"] = relationship(  # noqa: F821
        "EntityStatus",
        lazy="joined",
    )

    # Self-referential — unidirectional, points to immediate parent only.
    # Replies are never traversed from the parent side in this service;
    # they are always fetched via a direct query (GET /comments?parent_id=).
    # ``foreign_keys`` disambiguates the FK side for SQLAlchemy.
    parent: Mapped["Comment | None"] = relationship(
        "Comment",
        foreign_keys="[Comment.parent_comment_id]",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Comment id={self.id} thread={self.thread_id}>"
