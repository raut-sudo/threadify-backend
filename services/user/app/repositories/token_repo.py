"""
Repository layer for RefreshToken database operations.

Handles creation, lookup, and revocation of opaque refresh tokens.
Each token is a random UUID hex stored as a string — validation is
done purely by DB lookup, not cryptographic verification.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)


async def create_refresh_token(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    token: str,
    expires_days: int = 7,
) -> RefreshToken:
    """Persist a new refresh token for the given user.

    The expiry is computed as now + expires_days. The caller
    generates the opaque token string via security.generate_refresh_token().
    """
    rt = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=datetime.now(UTC) + timedelta(days=expires_days),
    )
    db.add(rt)
    await db.flush()
    logger.info("Refresh token created: user_id=%s", user_id)
    return rt


async def get_refresh_token(db: AsyncSession, token: str) -> RefreshToken | None:
    """Look up a refresh token by its opaque string value.

    Returns None if no matching token exists in the database.
    """
    stmt = select(RefreshToken).where(RefreshToken.token == token)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_token(db: AsyncSession, refresh_token: RefreshToken) -> None:
    """Mark a single refresh token as revoked.

    Used during logout and token rotation — the old token becomes
    unusable but remains in the DB for audit purposes.
    """
    refresh_token.revoked = True
    await db.flush()
    logger.info("Refresh token revoked: id=%s", refresh_token.id)


async def revoke_all_user_tokens(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Revoke every active refresh token belonging to a user.

    Returns the number of tokens revoked. Used on password change,
    account ban, or an explicit "logout everywhere" action.
    """
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
        .values(revoked=True)
    )
    result = await db.execute(stmt)
    count = result.rowcount
    await db.flush()
    logger.info("Revoked %d refresh tokens for user_id=%s", count, user_id)
    return count
