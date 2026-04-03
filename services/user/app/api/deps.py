"""
Shared FastAPI dependencies for the API layer.

Provides the ``get_current_user`` dependency that extracts a Bearer JWT
from the *Authorization* header, verifies it, and loads the
corresponding User from the database.  Inject it via ``Depends`` in any
route that requires authentication.
"""

import logging
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.repositories import user_repo
from app.utils.constants import (
    ERR_ACCOUNT_DELETED,
    ERR_INVALID_ACCESS_TOKEN,
    ERR_USER_NOT_FOUND,
)
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_INVALID_ACCESS_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_INVALID_ACCESS_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = await user_repo.get_user_by_id(db, uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_USER_NOT_FOUND,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERR_ACCOUNT_DELETED,
        )

    return user
