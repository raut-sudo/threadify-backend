"""
Admin routes — role management and user banning.

All endpoints require the ADMIN role via the ``require_admin``
dependency.  Guards in the service layer prevent admins from
modifying other admins or themselves.
"""

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import RoleUpdateRequest, UserResponse
from app.services import user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["Admin"])


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
    summary="Change a user's role (MEMBER ↔ MOD)",
)
async def change_user_role(
    user_id: uuid.UUID,
    body: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Promote a MEMBER to MOD or demote a MOD to MEMBER.

    Cannot target admins or yourself.
    """
    updated = await user_service.change_user_role(
        db,
        target_user_id=user_id,
        role_name=body.role,
        admin=admin,
    )
    return updated


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Ban (soft-delete) a user",
)
async def ban_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Soft-delete a user and revoke all their sessions.

    Cannot target admins or yourself.
    """
    await user_service.ban_user(
        db,
        target_user_id=user_id,
        admin=admin,
    )
    return MessageResponse(message="User banned successfully")
