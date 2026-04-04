"""
User routes — profile management, self-deletion, and user listing.

All endpoints require Bearer token authentication via the
``get_current_user`` dependency.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import UserListResponse, UserResponse, UserUpdate
from app.services import user_service
from app.utils.constants import DEFAULT_PAGE_LIMIT, DEFAULT_PAGE_SKIP

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the authenticated user's profile",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Return the profile of the currently authenticated user.

    The user (with eagerly loaded role) is resolved by the auth
    dependency — no additional DB query is needed.
    """
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update the authenticated user's profile",
)
async def update_my_profile(
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply partial updates to the authenticated user's profile.

    Only the fields present in the request body are updated.
    Uniqueness constraints on username and email are enforced.
    """
    updated = await user_service.update_profile(
        db,
        user=current_user,
        username=body.username,
        email=body.email,
        password=body.password,
    )
    return updated


@router.delete(
    "/me",
    response_model=MessageResponse,
    summary="Delete the authenticated user's account",
)
async def delete_my_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete the account and revoke all active sessions.

    The user row is retained for audit / foreign-key integrity but
    the account can no longer authenticate.
    """
    await user_service.delete_account(db, user=current_user)
    return MessageResponse(message="Account deleted successfully")


@router.get(
    "/",
    response_model=UserListResponse,
    summary="List all users (paginated)",
)
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(
        default=DEFAULT_PAGE_SKIP,
        ge=0,
        description="Number of rows to skip",
    ),
    limit: int = Query(
        default=DEFAULT_PAGE_LIMIT,
        ge=1,
        le=100,
        description="Maximum number of rows to return",
    ),
    _current_user: User = Depends(get_current_user),
):
    """Return a paginated list of users with total count.

    Requires authentication. Results are ordered newest-first.
    """
    users, total = await user_service.list_users(db, skip=skip, limit=limit)
    return UserListResponse(users=users, total=total)
