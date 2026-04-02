"""
Higher-level token helpers that wrap app/core/security.py.

Used by services and dependencies — keeps security.py focused on raw
crypto while this module handles token-pair generation and type-safe
verification.
"""

import logging

from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)

logger = logging.getLogger(__name__)


def generate_tokens(user_id: str) -> dict:
    """Generate an access + refresh token pair for a user."""
    access = create_access_token(subject=user_id)
    refresh = create_refresh_token(subject=user_id)
    logger.info("Token pair generated: user_id=%s", user_id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


def verify_access_token(token: str) -> str | None:
    """Verify an access token. Returns user_id or None."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            logger.warning(
                "Token type mismatch: expected 'access', got '%s'",
                payload.get("type"),
            )
            return None
        return payload.get("sub")
    except JWTError:
        return None


def verify_refresh_token(token: str) -> str | None:
    """Verify a refresh token. Returns user_id or None."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            logger.warning(
                "Token type mismatch: expected 'refresh', got '%s'",
                payload.get("type"),
            )
            return None
        return payload.get("sub")
    except JWTError:
        return None
