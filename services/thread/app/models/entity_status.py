"""EntityStatus ORM model — shared status lookup table.

Storing statuses in a table (rather than a PostgreSQL ENUM) means:
  - New statuses can be added at runtime without schema migrations.
  - Both threads and comments reference the same table, keeping a
    single source of truth for valid status values.

Seeded values on startup: ACTIVE · USER_DELETED · MOD_REMOVED
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EntityStatus(Base):
    """A named content-lifecycle state shared by threads and comments.

    The 'name' column is the canonical identifier used in business
    logic and JWT claims (e.g. ``STATUS_ACTIVE = "ACTIVE"``).
    """

    __tablename__ = "entity_status"

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

    def __repr__(self) -> str:
        return f"<EntityStatus {self.name}>"
