"""
Higher-level token helpers that wrap app/core/security.py.

Used by services and dependencies — keeps security.py focused on raw
crypto while this module handles token-pair generation and type-safe
verification.

Refresh tokens are opaque UUIDs stored in the database, so there is no
cryptographic verification function for them here — validation happens
via DB lookup in the service layer.
"""

import logging

from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_token,
    generate_refresh_token,
)

logger = logging.getLogger(__name__)


def generate_tokens(user_id: str) -> dict:
    """Generate an access token + opaque refresh token pair."""
    access = create_access_token(subject=user_id)
    refresh = generate_refresh_token()
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
