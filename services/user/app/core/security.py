"""
Security utilities for the user service.

Provides password hashing (Argon2), RS256 JWT creation/verification.
This is the low-level crypto layer — higher-level token helpers live
in app/utils/token.py.
"""

import logging
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from jose import JWTError, jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Password Hashing ────────────────────────────────

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using Argon2id."""
    hashed = _hasher.hash(plain_password)
    logger.debug("Password hashed successfully")
    return hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored Argon2 hash."""
    try:
        result = _hasher.verify(hashed_password, plain_password)
    except VerificationError:
        result = False
    logger.debug(
        "Password verification: %s",
        "success" if result else "failed",
    )
    return result


# ── RSA Key Loading ─────────────────────────────────


def _load_key(raw: str) -> str:
    """Convert env-var PEM string (escaped newlines) to real PEM."""
    return raw.replace("\\n", "\n")


PRIVATE_KEY = _load_key(settings.RSA_PRIVATE_KEY)
PUBLIC_KEY = _load_key(settings.RSA_PUBLIC_KEY)


# ── JWT Creation ────────────────────────────────────


def create_access_token(
    subject: str,
    extra_claims: dict | None = None,
) -> str:
    """Create an RS256-signed access token (short-lived)."""
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    payload = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(
        payload,
        PRIVATE_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    logger.info(
        "Access token created: subject=%s, expires=%s",
        subject,
        expire,
    )
    return token


def create_refresh_token(subject: str) -> str:
    """Create an RS256-signed refresh token (long-lived)."""
    expire = datetime.now(UTC) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )
    payload = {"sub": subject, "exp": expire, "type": "refresh"}

    token = jwt.encode(
        payload,
        PRIVATE_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    logger.info("Refresh token created: subject=%s", subject)
    return token


# ── JWT Verification ────────────────────────────────


def decode_token(token: str) -> dict:
    """Decode and verify a JWT using the PUBLIC key.

    Returns the payload dict on success.
    Raises JWTError on any failure (expired, tampered, malformed).
    """
    try:
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        logger.debug(
            "Token decoded: sub=%s, type=%s",
            payload.get("sub"),
            payload.get("type"),
        )
        return payload
    except JWTError as e:
        logger.warning("Token decode failed: %s", e)
        raise
