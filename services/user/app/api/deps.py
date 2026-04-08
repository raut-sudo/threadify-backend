"""
Shared FastAPI dependencies for the API layer.

Provides the ``get_current_user`` dependency that extracts a Bearer JWT
from the *Authorization* header, verifies it, and loads the
corresponding User from the database.  Inject it via ``Depends`` in any
route that requires authentication.
"""

import logging
import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import (
    AccountDeletedError,
    InsufficientPermissionsError,
    InvalidAccessTokenError,
)
from app.models.user import User
from app.repositories import user_repo
from app.utils.constants import ROLE_ADMIN
from app.utils.token import verify_access_token

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the Bearer token, returning the authenticated User.

    Raises:
        HTTPException 401: Token is missing, invalid, expired, or the user
            no longer exists.
        HTTPException 403: The user's account has been deleted.
    """
    user_id = verify_access_token(credentials.credentials)
    if user_id is None:
        raise InvalidAccessTokenError()

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise InvalidAccessTokenError() from None

    user = await user_repo.get_user_by_id(db, uid)
    if not user:
        raise InvalidAccessTokenError()

    if user.deleted:
        raise AccountDeletedError()

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the authenticated user has the ADMIN role.

    Chains on ``get_current_user`` — token validation and account
    checks happen first, then this adds the role gate.

    Raises:
        InsufficientPermissionsError (403): User is not an admin.
    """
    if current_user.role.name != ROLE_ADMIN:
        raise InsufficientPermissionsError()
    return current_user
