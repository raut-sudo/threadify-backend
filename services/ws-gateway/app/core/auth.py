"""JWT verification for the WS gateway.

This service only *verifies* tokens — it never issues them.
Tokens are RS256-signed by the user service and carry:

    sub      — user_id (UUID string)
    role     — "ADMIN" | "MOD" | "MEMBER"
    username — display name
    type     — must be "access"
    exp      — expiry timestamp

Usage
-----
Pass the bearer token from the Socket.IO ``auth`` dict on connect::

    claims = verify_token(auth.get("token"))
    if claims is None:
        raise ConnectionRefusedError("authentication failed")
"""

import logging

from jose import JWTError, jwt

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Normalise the PEM string once at import time.
# Stored in .env with literal \n; python-jose needs real newlines.
_PUBLIC_KEY: str = settings.RSA_PUBLIC_KEY.replace("\\n", "\n")

_ACCESS_TYPE = "access"


def verify_token(token: str) -> dict | None:
    """Decode and verify an RS256 access token.

    Returns ``{"user_id": str, "role": str, "username": str}`` on success,
    or ``None`` on any failure (expired, tampered, wrong type, etc.).
    Returning None instead of raising keeps ``rooms.connect`` clean.
    """
    try:
        payload = jwt.decode(
            token,
            _PUBLIC_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )

        if payload.get("type") != _ACCESS_TYPE:
            logger.warning("Token rejected: wrong type=%s", payload.get("type"))
            return None

        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token rejected: missing sub")
            return None

        return {
            "user_id": user_id,
            "role": payload.get("role", "MEMBER"),
            "username": payload.get("username", ""),
        }

    except JWTError as exc:
        logger.warning("Token rejected: %s", exc)
        return None
