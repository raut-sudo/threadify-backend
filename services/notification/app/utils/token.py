"""JWT verification utility for the notification service.

This service only *verifies* tokens — it never issues them.
"""

import logging
import uuid

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidAccessTokenError
from app.utils.constants import TOKEN_TYPE_ACCESS

logger = logging.getLogger(__name__)

settings = get_settings()

_PUBLIC_KEY: str = settings.RSA_PUBLIC_KEY.replace("\\n", "\n")


def decode_access_token(token: str) -> dict:
    """Decode and verify an RS256 access token.

    Returns a dict with ``user_id`` (UUID) and ``role`` (str) on success.
    Raises ``InvalidAccessTokenError`` (401) on any failure.
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

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        logger.warning("Token type mismatch: expected '%s'", TOKEN_TYPE_ACCESS)
        raise InvalidAccessTokenError()

    user_id_raw = payload.get("sub")
    role = payload.get("role")

    if not user_id_raw or not role:
        logger.warning(
            "Token missing required claims: sub=%s, role=%s", user_id_raw, role
        )
        raise InvalidAccessTokenError()

    try:
        user_id = uuid.UUID(user_id_raw)
    except ValueError as exc:
        logger.warning("Token sub is not a valid UUID: %s", user_id_raw)
        raise InvalidAccessTokenError() from exc

    logger.debug("Token verified: user_id=%s, role=%s", user_id, role)
    return {"user_id": user_id, "role": role}
