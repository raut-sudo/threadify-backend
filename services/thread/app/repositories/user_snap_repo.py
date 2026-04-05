"""Repository layer for UserSnap database operations.

Pure data-access — no business logic, no HTTP concerns.

UserSnap rows are the denormalized author display cache.  The typical
lifecycle is:
  1. An inter-service event (or temporary test endpoint) calls ``upsert_user_snap``.
  2. Thread / comment responses embed the snap via ``get_user_snap``.
  3. If a user is deleted in the user service, ``delete_user_snap`` removes the row.

Upsert strategy
---------------
Rather than a full PostgreSQL ``INSERT … ON CONFLICT DO UPDATE``, we use
a simple select-then-insert-or-update pattern so the code stays portable
and readable.  Given the low write frequency (profile updates) this is
perfectly acceptable.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_snap import UserSnap

logger = logging.getLogger(__name__)


async def get_user_snap(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> UserSnap | None:
    """Fetch a user snapshot by user_id.

    Returns ``None`` if no snapshot exists for this user yet.
    """
    stmt = select(UserSnap).where(UserSnap.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_user_snap(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    username: str,
    avatar_url: str | None = None,
) -> UserSnap:
    """Create a new user snapshot or update the existing one.

    If a row already exists for ``user_id``, only the provided
    non-``None`` fields are overwritten.  ``updated_at`` is always
    refreshed to reflect the latest change time.
    """
    snap = await get_user_snap(db, user_id)

    if snap is None:
        snap = UserSnap(
            user_id=user_id,
            username=username,
            avatar_url=avatar_url,
        )
        db.add(snap)
        logger.info("UserSnap created: user_id=%s username=%s", user_id, username)
    else:
        snap.username = username
        if avatar_url is not None:
            snap.avatar_url = avatar_url
        snap.updated_at = datetime.now(UTC)
        logger.info("UserSnap updated: user_id=%s username=%s", user_id, username)

    await db.flush()
    return snap


async def delete_user_snap(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Hard-delete a user snapshot row.

    Called when a user account is deleted in the user service so stale
    author data is not displayed alongside orphaned threads / comments.
    """
    snap = await get_user_snap(db, user_id)
    if snap is not None:
        await db.delete(snap)
        await db.flush()
        logger.info("UserSnap deleted: user_id=%s", user_id)
