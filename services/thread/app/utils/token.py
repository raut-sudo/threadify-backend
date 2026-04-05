"""JWT verification utility for the thread service.

This service only *verifies* tokens — it never issues them.
Tokens are created by the user service and signed with its RSA private
key; this service validates them using the corresponding public key.

The JWT payload (as issued by the user service) contains:
    sub      — user_id (UUID string)
    role     — role name ("ADMIN" | "MOD" | "MEMBER")
    username — display name (available but not required for auth)
    type     — must be "access"
    exp      — expiry timestamp (validated automatically by jose)

Usage
-----
Call ``decode_access_token`` in the ``get_current_user`` dependency::

    payload = decode_access_token(token)
    # → {"user_id": UUID("..."), "role": "ADMIN"}
    # Raises InvalidAccessTokenError (401) on any failure — no None checks needed.
"""

import logging
import uuid

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidAccessTokenError
from app.utils.constants import TOKEN_TYPE_ACCESS

logger = logging.getLogger(__name__)

settings = get_settings()

# Normalise the PEM string once at import time.
# The public key is stored in .env with literal \n sequences;
# python-jose requires real newlines in the PEM header/body.
_PUBLIC_KEY: str = settings.RSA_PUBLIC_KEY.replace("\\n", "\n")


def decode_access_token(token: str) -> dict:
    """Decode and verify an RS256 access token.

    Returns a dict with ``user_id`` (UUID) and ``role`` (str) on success.
    Raises ``InvalidAccessTokenError`` (401) on any failure so callers
    (e.g. ``deps.get_current_user``) stay thin — no ``None`` checks needed.

    Failure cases covered:
    - Malformed / tampered / expired JWT
    - Token ``type`` claim is not ``"access"``
    - Missing ``sub`` or ``role`` claims
    - ``sub`` is not a valid UUID
    """
    try:
        payload = jwt.decode(
            token,
            _PUBLIC_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise InvalidAccessTokenError() from exc

    # Reject non-access tokens (e.g. if someone passes a refresh token)
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        logger.warning(
            "Token type mismatch: expected '%s', got '%s'",
            TOKEN_TYPE_ACCESS,
            payload.get("type"),
        )
        raise InvalidAccessTokenError()

    user_id_raw = payload.get("sub")
    role = payload.get("role")

    if not user_id_raw or not role:
        logger.warning(
            "Token missing required claims: sub=%s, role=%s",
            user_id_raw,
            role,
        )
        raise InvalidAccessTokenError()

    try:
        user_id = uuid.UUID(user_id_raw)
    except ValueError as exc:
        logger.warning("Token sub is not a valid UUID: %s", user_id_raw)
        raise InvalidAccessTokenError() from exc

    logger.debug("Token verified: user_id=%s, role=%s", user_id, role)
    return {"user_id": user_id, "role": role}
