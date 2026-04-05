"""UserSnap service — business logic for user snapshot management.

User snapshots are the denormalized author display data embedded in
thread and comment responses.  In production they are populated via
inter-service events; these endpoints exist for local testing.

Every public function receives an ``AsyncSession`` and raises a domain
``AppException`` on failure.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserSnapNotFoundError
from app.repositories import user_snap_repo
from app.schemas.user_snap import UserSnapCreate, UserSnapUpdate

logger = logging.getLogger(__name__)


async def create_or_update_snap(
    db: AsyncSession,
    *,
    data: UserSnapCreate,
) -> object:
    """Upsert a user snapshot.

    Creates the row if it doesn't exist, otherwise updates only the
    fields provided in ``data``.  Returns the persisted ``UserSnap``.
    """
    snap = await user_snap_repo.upsert_user_snap(
        db,
        user_id=data.user_id,
        username=data.username,
        avatar_url=data.avatar_url,
    )
    logger.info("UserSnap upserted: user_id=%s", data.user_id)
    return snap


async def update_snap(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: UserSnapUpdate,
) -> object:
    """Partially update an existing user snapshot.

    Raises ``UserSnapNotFoundError`` if no snapshot exists for the user.
    Only non-``None`` fields in ``data`` are applied.
    """
    snap = await user_snap_repo.get_user_snap(db, user_id)
    if snap is None:
        raise UserSnapNotFoundError()

    update_fields: dict = {}
    if data.username is not None:
        update_fields["username"] = data.username
    if data.avatar_url is not None:
        update_fields["avatar_url"] = data.avatar_url

    for key, value in update_fields.items():
        setattr(snap, key, value)

    logger.info("UserSnap updated: user_id=%s fields=%s", user_id, list(update_fields))
    return snap


async def get_snap(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> object:
    """Return a user snapshot or raise ``UserSnapNotFoundError``."""
    snap = await user_snap_repo.get_user_snap(db, user_id)
    if snap is None:
        raise UserSnapNotFoundError()
    return snap
