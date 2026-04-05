"""Seed function for the entity_status lookup table.

Called once at application startup (inside the ``lifespan`` handler in
``main.py``) to ensure the three required status values exist before any
thread or comment is created.  Safe to re-run — existing rows are skipped.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity_status import EntityStatus
from app.utils.constants import STATUS_ACTIVE, STATUS_MOD_REMOVED, STATUS_USER_DELETED

logger = logging.getLogger(__name__)

# (name, description) pairs — order matters only for readability in the DB.
_STATUSES: list[tuple[str, str]] = [
    (STATUS_ACTIVE, "Content is publicly visible"),
    (STATUS_USER_DELETED, "Soft-deleted by the author; content shown as [deleted]"),
    (STATUS_MOD_REMOVED, "Removed by a moderator or admin; hidden from regular users"),
]


async def seed_entity_statuses(db: AsyncSession) -> None:
    """Insert ACTIVE, USER_DELETED, MOD_REMOVED if not already present.

    Uses individual name lookups so partial seeds (e.g. after adding a new
    status in a future release) are handled gracefully without touching
    already-existing rows.
    """
    for name, description in _STATUSES:
        stmt = select(EntityStatus).where(EntityStatus.name == name)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if not existing:
            db.add(EntityStatus(name=name, description=description))
            logger.info("Seeded entity status: %s", name)

    await db.flush()
    logger.info("Entity status seed complete")
