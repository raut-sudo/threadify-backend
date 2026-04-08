"""
Role ORM model — represents user roles as a database table.

Storing roles in a table (instead of a Python enum) allows adding,
renaming, or deactivating roles at runtime without code changes or
schema migrations. Each user references a role via foreign key.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Role(Base):
    """A named permission tier (ADMIN / MOD / MEMBER).

    Seeded on first startup via create_all or a seed script.
    The 'name' column is the canonical lookup key used across
    the codebase (e.g. in JWT claims and permission checks).
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # ── Relationships ───────────────────────────────
    users: Mapped[list["User"]] = relationship(  # noqa: F821
        back_populates="role",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Role {self.name}>"
