"""UserSnap API routes.

User snapshots are the denormalized author data (username, avatar) that
are embedded in thread and comment responses.  In production they are
populated by an inter-service event consumer; these endpoints exist for
local development and testing.

Endpoints
---------
POST  /user-snaps              — upsert a user snapshot (authenticated)
GET   /user-snaps/{user_id}    — fetch a user snapshot (public)
PATCH /user-snaps/{user_id}    — update a user snapshot (owner only)
"""

import logging
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotAuthorizedError
from app.schemas.user_snap import UserSnapCreate, UserSnapResponse, UserSnapUpdate
from app.services import user_snap_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user-snaps", tags=["UserSnaps"])


@router.post("", response_model=UserSnapResponse, status_code=status.HTTP_201_CREATED)
async def create_user_snap(
    payload: UserSnapCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserSnapResponse:
    """Upsert a user snapshot.

    The ``user_id`` in the request body must match the authenticated
    user's ID unless the caller is an admin.  Creates the row when it
    does not yet exist, otherwise updates it.
    """
    if payload.user_id != current_user["user_id"]:
        raise NotAuthorizedError()

    snap = await user_snap_service.create_or_update_snap(db, data=payload)
    return UserSnapResponse.model_validate(snap)


@router.get("/{user_id}", response_model=UserSnapResponse)
async def get_user_snap(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UserSnapResponse:
    """Fetch a user snapshot by user ID.  No authentication required."""
    snap = await user_snap_service.get_snap(db, user_id=user_id)
    return UserSnapResponse.model_validate(snap)


@router.patch("/{user_id}", response_model=UserSnapResponse)
async def update_user_snap(
    user_id: uuid.UUID,
    payload: UserSnapUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserSnapResponse:
    """Partially update a user snapshot.

    The authenticated user may only update their own snapshot.
    Raises 403 when ``user_id`` does not match the token subject.
    """
    if user_id != current_user["user_id"]:
        raise NotAuthorizedError()

    snap = await user_snap_service.update_snap(db, user_id=user_id, data=payload)
    return UserSnapResponse.model_validate(snap)
