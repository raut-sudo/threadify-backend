"""Seed function for the entity_status lookup table.

Called once at application startup (inside the ``lifespan`` handler in
``main.py``) to ensure the three required status values exist before any
thread or comment is created.  Safe to re-run — existing rows are skipped.
"""

import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity_status import EntityStatus
from app.utils.constants import STATUS_ACTIVE, STATUS_MOD_REMOVED, STATUS_USER_DELETED

logger = logging.getLogger(__name__)

# In-memory cache populated once at startup by ``seed_entity_statuses``.
# Maps status name → UUID.  Avoids a DB round-trip on every create/delete.
_status_id_cache: dict[str, "uuid.UUID"] = {}

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

    # Populate the in-memory cache so service-layer lookups never hit the DB.
    for name, _ in _STATUSES:
        row = (
            await db.execute(select(EntityStatus).where(EntityStatus.name == name))
        ).scalar_one()
        _status_id_cache[row.name] = row.id
    logger.info("Entity status seed complete (cache: %s)", list(_status_id_cache))


async def seed_search_trigger(db: AsyncSession) -> None:
    """Create or replace the tsvector auto-update trigger on the threads table.

    Idempotent — safe to call on every startup.  The trigger keeps
    ``search_vector`` in sync with ``title`` and ``content`` so the
    application never needs to update it manually.
    """
    await db.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION threads_search_vector_update()
            RETURNS trigger AS $$
            BEGIN
                NEW.search_vector :=
                    setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    await db.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_threads_search_vector'
                ) THEN
                    CREATE TRIGGER trg_threads_search_vector
                    BEFORE INSERT OR UPDATE OF title, content
                    ON threads
                    FOR EACH ROW
                    EXECUTE FUNCTION threads_search_vector_update();
                END IF;
            END;
            $$;
            """
        )
    )
    # Backfill any existing rows that have a NULL search_vector
    await db.execute(
        text(
            """
            UPDATE threads
            SET search_vector =
                setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(content, '')), 'B')
            WHERE search_vector IS NULL;
            """
        )
    )
    logger.info("Search vector trigger seeded")


def get_cached_status_id(name: str) -> uuid.UUID | None:
    """Return the cached UUID for a status name, or None if not cached.

    The cache is populated at startup by ``seed_entity_statuses``.
    This avoids a DB round-trip on every thread/comment create and delete.
    """
    return _status_id_cache.get(name)


async def get_entity_status_by_name(
    db: AsyncSession,
    name: str,
) -> EntityStatus | None:
    """Return the EntityStatus row with the given name, or None.

    Used by the service layer to resolve status IDs (ACTIVE,
    USER_DELETED, MOD_REMOVED) before writing to threads/comments.
    """
    stmt = select(EntityStatus).where(EntityStatus.name == name)
    return (await db.execute(stmt)).scalar_one_or_none()
