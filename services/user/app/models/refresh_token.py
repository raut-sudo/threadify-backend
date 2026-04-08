"""
RefreshToken ORM model — opaque tokens stored server-side.

Each token is a random UUID hex string. Validation is done by
database lookup (not cryptographic verification). Expiry and
revocation are tracked here so the service layer can enforce
rotation and TTL policies.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RefreshToken(Base):
    """An opaque refresh token bound to a specific user.

    Tokens are looked up by their 'token' column value. The 'revoked'
    flag enables soft-revocation (e.g. on logout or password change)
    and the 'is_expired' property gives a quick staleness check.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_refresh_token"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # ── Relationships ───────────────────────────────
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="refresh_tokens",
    )

    def __repr__(self) -> str:
        return f"<RefreshToken user_id={self.user_id} revoked={self.revoked}>"

    @property
    def is_expired(self) -> bool:
        """Return True if the token's TTL has elapsed."""
        return datetime.now(UTC) >= self.expires_at
