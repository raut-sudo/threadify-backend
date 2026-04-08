"""User service — profile management and self-deletion."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountAlreadyDeletedError,
    CannotModifyAdminError,
    CannotModifySelfError,
    EmailAlreadyRegisteredError,
    InvalidRoleError,
    UsernameTakenError,
    UserNotFoundError,
    WrongPasswordError,
)
from app.core.security import hash_password, verify_password
from app.events import publisher as user_publisher
from app.events.payloads import UserSnapEvent
from app.models.user import User
from app.repositories import token_repo, user_repo
from app.utils.constants import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_SKIP,
    ROLE_ADMIN,
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


# ── Change Password ─────────────────────────────────


async def change_password(
    db: AsyncSession,
    *,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """Verify the current password and update to the new one.

    Raises ``WrongPasswordError`` if the current password doesn't match.
    """
    if not verify_password(current_password, user.hashed_password):
        raise WrongPasswordError()

    await user_repo.update_user(
        db,
        user,
        hashed_password=hash_password(new_password),
    )
    logger.info("Password changed for user: %s", user.username)


async def update_profile(
    db: AsyncSession,
    *,
    user: User,
    username: str | None = None,
    email: str | None = None,
    password: str | None = None,
    bio: str | None = ...,
    avatar_url: str | None = ...,
) -> User:
    """Apply partial updates to the authenticated user's profile.

    Checks for uniqueness conflicts on username/email before
    writing. If a new password is supplied it is hashed first.
    Bio and avatar_url use sentinel ``...`` so we can distinguish
    "not provided" from "explicitly set to None".
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

    # Bio: None clears it, string sets it, ... (sentinel) means not provided
    if bio is not ...:
        fields["bio"] = bio

    # Avatar URL: None clears it, string sets it, ... means not provided
    if avatar_url is not ...:
        fields["avatar_url"] = avatar_url

    if not fields:
        return user

    updated = await user_repo.update_user(db, user, **fields)
    logger.info("Profile updated: %s", updated.username)

    if "username" in fields or "avatar_url" in fields:
        await user_publisher.publish(
            "user.updated",
            UserSnapEvent(
                event_type="user.updated",
                user_id=str(updated.id),
                username=updated.username,
                avatar_url=updated.avatar_url,
            ),
        )

    return updated


# ── User Listing ────────────────────────────────────


async def list_users(
    db: AsyncSession,
    *,
    skip: int = DEFAULT_PAGE_SKIP,
    limit: int = DEFAULT_PAGE_LIMIT,
    role: str | None = None,
    search: str | None = None,
    deleted: bool | None = False,
) -> tuple[list[User], int]:
    """Return a paginated, filterable list of users with total count.

    Sorting is newest-first by default.  Filters are passed through
    to the repository layer.
    """
    users, total = await user_repo.list_users(
        db,
        skip=skip,
        limit=limit,
        role=role,
        search=search,
        deleted=deleted,
    )
    return users, total


# ── Admin Operations ────────────────────────────────


async def change_user_role(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    role_name: str,
    admin: User,
) -> User:
    """Change a user's role (MEMBER ↔ MOD). Admin-only.

    Guards:
        - Cannot modify yourself.
        - Cannot modify another admin.
        - Target role must be MEMBER or MOD.
    """
    if target_user_id == admin.id:
        raise CannotModifySelfError()

    target = await user_repo.get_user_by_id(db, target_user_id)
    if not target:
        raise UserNotFoundError()

    if target.role.name == ROLE_ADMIN:
        raise CannotModifyAdminError()

    if role_name not in ("MEMBER", "MOD"):
        raise InvalidRoleError()

    role = await user_repo.get_role_by_name(db, role_name)
    if not role:
        raise InvalidRoleError()

    updated = await user_repo.update_user(db, target, role_id=role.id)
    logger.info(
        "Role changed: %s → %s (by admin %s)",
        target.username,
        role_name,
        admin.username,
    )
    return updated


async def ban_user(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    admin: User,
) -> User:
    """Ban (soft-delete) a user. Admin-only.

    Guards:
        - Cannot ban yourself.
        - Cannot ban another admin.
        - Cannot ban an already-deleted user.
    """
    if target_user_id == admin.id:
        raise CannotModifySelfError()

    target = await user_repo.get_user_by_id(db, target_user_id)
    if not target:
        raise UserNotFoundError()

    if target.role.name == ROLE_ADMIN:
        raise CannotModifyAdminError()

    if target.deleted:
        raise AccountAlreadyDeletedError()

    updated = await user_repo.soft_delete_user(db, target)
    await token_repo.revoke_all_user_tokens(db, target.id)
    logger.info(
        "User banned: %s (by admin %s)",
        target.username,
        admin.username,
    )
    return updated


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
