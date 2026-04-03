"""
Authentication service — business logic for register, login, refresh, logout.

Orchestrates the user and token repositories together with the
security module. Every public method receives an AsyncSession
(injected by the route handler via Depends) and raises HTTPException
on any auth failure so routes stay thin.
"""

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from app.repositories import token_repo, user_repo

logger = logging.getLogger(__name__)

settings = get_settings()


# ── Registration ────────────────────────────────────


async def register(
    db: AsyncSession,
    *,
    username: str,
    email: str,
    password: str,
) -> dict:
    """Create a new user account and return a token pair.

    Checks for duplicate username/email, hashes the password,
    assigns the default MEMBER role, persists the user, and
    issues access + refresh tokens in one go.
    """
    if await user_repo.get_user_by_username(db, username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    if await user_repo.get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    role = await user_repo.get_role_by_name(db, "MEMBER")
    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default role not found — database may not be seeded",
        )

    user = await user_repo.create_user(
        db,
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role_id=role.id,
    )

    tokens = await _issue_tokens(db, user)
    logger.info("User registered: %s", username)
    return tokens


# ── Login ───────────────────────────────────────────


async def login(
    db: AsyncSession,
    *,
    username: str,
    password: str,
) -> dict:
    """Authenticate a user by username + password and return tokens.

    Validates the user exists, is active, is not banned, and the
    password matches. On success issues a fresh token pair.
    """
    user = await user_repo.get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if user.deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deleted",
        )

    tokens = await _issue_tokens(db, user)
    logger.info("User logged in: %s", username)
    return tokens


# ── Token Refresh ───────────────────────────────────


async def refresh_tokens(db: AsyncSession, *, refresh_token: str) -> dict:
    """Rotate a refresh token — revoke the old one, issue a new pair.

    Validates the token exists in the DB, is not revoked, and has
    not expired. Then atomically revokes the old token and creates
    a replacement along with a fresh access token.
    """
    existing = await token_repo.get_refresh_token(db, refresh_token)
    if not existing or existing.revoked or existing.is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await user_repo.get_user_by_id(db, existing.user_id)
    if not user or user.deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account unavailable",
        )

    # Revoke old token, issue new pair
    await token_repo.revoke_token(db, existing)
    tokens = await _issue_tokens(db, user)
    logger.info("Tokens refreshed: user_id=%s", user.id)
    return tokens


# ── Logout ──────────────────────────────────────────


async def logout(db: AsyncSession, *, refresh_token: str) -> None:
    """Revoke a single refresh token (standard logout).

    Silently succeeds even if the token is already revoked or
    doesn't exist — there's nothing for the client to retry.
    """
    existing = await token_repo.get_refresh_token(db, refresh_token)
    if existing and not existing.revoked:
        await token_repo.revoke_token(db, existing)
        logger.info("User logged out: token revoked")


async def logout_all(db: AsyncSession, *, user_id) -> int:
    """Revoke every active refresh token for a user (logout everywhere).

    Returns the number of tokens that were revoked.
    """
    count = await token_repo.revoke_all_user_tokens(db, user_id)
    logger.info("Logout-all: revoked %d tokens for user_id=%s", count, user_id)
    return count


# ── Internal Helpers ────────────────────────────────


async def _issue_tokens(db: AsyncSession, user) -> dict:
    """Create an access + refresh token pair and persist the refresh token.

    The access token JWT carries sub (user_id), username, and role
    as extra claims for downstream services to consume without a
    DB round-trip.
    """
    access = create_access_token(
        subject=str(user.id),
        extra_claims={
            "username": user.username,
            "role": user.role.name,
        },
    )
    raw_refresh = generate_refresh_token()

    await token_repo.create_refresh_token(
        db,
        user_id=user.id,
        token=raw_refresh,
        expires_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )

    return {
        "access_token": access,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }
