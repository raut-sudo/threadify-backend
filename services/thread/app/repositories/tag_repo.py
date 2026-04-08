"""Tag repository — data-access layer for the tags table.

Provides upsert-style tag creation (``get_or_create_tags``) and a
simple listing function for the tag autocomplete endpoint.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag

logger = logging.getLogger(__name__)


async def get_or_create_tags(db: AsyncSession, tag_names: list[str]) -> list[Tag]:
    """Return Tag instances for each name, creating any that don't exist.

    Names are lowercased and stripped before lookup.  Duplicates in the
    input list are silently collapsed.
    """
    if not tag_names:
        return []

    # Normalise
    unique_names = list({name.lower().strip() for name in tag_names if name.strip()})
    if not unique_names:
        return []

    # Fetch existing
    stmt = select(Tag).where(Tag.name.in_(unique_names))
    result = await db.execute(stmt)
    existing = {tag.name: tag for tag in result.scalars().all()}

    # Create missing
    for name in unique_names:
        if name not in existing:
            tag = Tag(name=name)
            db.add(tag)
            existing[name] = tag

    await db.flush()
    return list(existing.values())


async def list_tags(
    db: AsyncSession,
    *,
    search: str | None = None,
    limit: int = 50,
) -> list[str]:
    """Return a list of tag names, optionally filtered by prefix search.

    Used by the ``GET /api/v1/tags`` autocomplete endpoint.
    """
    limit = min(limit, 100)
    stmt = select(Tag.name).order_by(Tag.name).limit(limit)

    if search:
        stmt = stmt.where(Tag.name.ilike(f"%{search.lower().strip()}%"))

    result = await db.execute(stmt)
    return list(result.scalars().all())
