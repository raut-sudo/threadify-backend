"""Shared FastAPI dependencies for the notification service API layer.

``get_current_user`` does not perform a database lookup — role and
identity are extracted directly from the verified JWT.
"""

import logging

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.utils.token import decode_access_token

logger = logging.getLogger(__name__)

_bearer_required = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_required),
) -> dict:
    """Verify the Bearer token and return the decoded payload.

    Returns ``{"user_id": UUID, "role": str}``.
    Raises ``InvalidAccessTokenError`` (401) on any failure.
    """
    return decode_access_token(credentials.credentials)
