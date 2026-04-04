"""User service — profile management and self-deletion."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountAlreadyDeletedError,
    EmailAlreadyRegisteredError,
    UsernameTakenError,
    UserNotFoundError,
)
from app.core.security import hash_password
from app.models.user import User
from app.repositories import token_repo, user_repo
from app.utils.constants import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_SKIP,
)

logger = logging.getLogger(__name__)


# ── Profile ─────────────────────────────────────────


async def get_profile(db: AsyncSession, *, user_id: uuid.UUID) -> User:
    """Return the full user profile for the given user_id.

    Raises 404 if the user doesn't exist or is deleted.
    """
    user = await user_repo.get_user_by_id(db, user_id)
    if not user or user.deleted:
        raise UserNotFoundError()
    return user


async def update_profile(
    db: AsyncSession,
    *,
    user: User,
    username: str | None = None,
    email: str | None = None,
    password: str | None = None,
) -> User:
    """Apply partial updates to the authenticated user's profile.

    Checks for uniqueness conflicts on username/email before
    writing. If a new password is supplied it is hashed first.
    """
    if (
        username
        and username != user.username
        and await user_repo.get_user_by_username(db, username)
    ):
        raise UsernameTakenError()

    if email and email != user.email and await user_repo.get_user_by_email(db, email):
        raise EmailAlreadyRegisteredError()

    fields: dict = {}
    if username:
        fields["username"] = username
    if email:
        fields["email"] = email
    if password:
        fields["hashed_password"] = hash_password(password)

    if not fields:
        return user

    updated = await user_repo.update_user(db, user, **fields)
    logger.info("Profile updated: %s", updated.username)
    return updated


# ── User Listing ────────────────────────────────────


async def list_users(
    db: AsyncSession,
    *,
    skip: int = DEFAULT_PAGE_SKIP,
    limit: int = DEFAULT_PAGE_LIMIT,
) -> tuple[list[User], int]:
    """Return a paginated list of all users with total count.

    Sorting is newest-first by default.
    """
    users, total = await user_repo.list_users(db, skip=skip, limit=limit)
    return users, total


# ── Self-Delete ─────────────────────────────────────


async def delete_account(db: AsyncSession, *, user: User) -> User:
    """User-initiated account deletion — sets deleted=True.

    Revokes all refresh tokens so active sessions end immediately.
    The row stays in the DB for audit / foreign-key integrity.
    """
    if user.deleted:
        raise AccountAlreadyDeletedError()

    updated = await user_repo.soft_delete_user(db, user)
    await token_repo.revoke_all_user_tokens(db, user.id)
    logger.info("User deleted account: %s", updated.username)
    return updated
