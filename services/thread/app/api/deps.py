"""Shared FastAPI dependencies for the thread service API layer.

The key difference from the user service: ``get_current_user`` does
**not** perform a database lookup.  Role and identity are extracted
directly from the verified JWT, as specified in §3 of the LLD.

This keeps authenticated endpoints fast — one crypto verify per request,
zero DB round-trips for auth.

Exported dependencies
---------------------
``get_current_user``         — requires a valid Bearer token; raises 401 otherwise.
``get_optional_current_user`` — returns the token payload if present, else ``None``.
                               Used by public endpoints (GET /threads,
                               GET /threads/{id}) that need ``is_liked``
                               populated when the user is logged in.
"""

import logging

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.utils.token import decode_access_token

logger = logging.getLogger(__name__)

# auto_error=False so we can return None for unauthenticated requests
# on public endpoints instead of raising immediately.
_bearer_required = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_required),
) -> dict:
    """Verify the Bearer token and return the decoded token payload.

    Returns a dict ``{"user_id": UUID, "role": str}`` on success.
    Raises ``InvalidAccessTokenError`` (401) on any token failure —
    ``decode_access_token`` handles all failure cases and raises directly.

    No database lookup is performed — role and identity come from the
    JWT claims issued by the user service.
    """
    return decode_access_token(credentials.credentials)


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
) -> dict | None:
    """Return the token payload if a valid Bearer token is provided, else ``None``.

    Used by public read endpoints (e.g. ``GET /threads``, ``GET /threads/{id}``)
    that want to enrich the response with ``is_liked=True`` when the caller
    is authenticated, but still serve unauthenticated callers normally.

    Token failures on an authenticated request still raise 401 — only the
    complete absence of a token yields ``None``.
    """
    if credentials is None:
        return None
    # decode_access_token raises InvalidAccessTokenError on bad tokens,
    # so a malformed token on a public endpoint is still rejected.
    return decode_access_token(credentials.credentials)
