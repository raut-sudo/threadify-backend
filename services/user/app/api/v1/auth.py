"""
Auth routes — registration, login, token refresh, and logout.

Refresh tokens are transported via httpOnly cookies for browser clients.
API clients that cannot use cookies may send the refresh token in the
JSON request body as a fallback.
"""

import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.auth import (
    AccessTokenResponse,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.services import auth_service
from app.utils.constants import (
    AUTH_COOKIE_PATH,
    ERR_REFRESH_TOKEN_REQUIRED,
    REFRESH_TOKEN_COOKIE,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Cookie Helpers ──────────────────────────────────


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set the refresh token as an httpOnly secure cookie."""
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=AUTH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Delete the refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        path=AUTH_COOKIE_PATH,
    )


# ── Endpoints ───────────────────────────────────────


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def signup(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Create a new account and return the user profile with an access token.

    The refresh token is set as an httpOnly cookie.
    """
    user, tokens = await auth_service.register(
        db,
        username=body.username,
        email=body.email,
        password=body.password,
    )
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=tokens["access_token"],
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate and obtain tokens",
)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Verify credentials and return the user profile with an access token.

    The refresh token is set as an httpOnly cookie.
    """
    user, tokens = await auth_service.login(
        db,
        username=body.username,
        password=body.password,
    )
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AuthResponse(
        user=UserResponse.model_validate(user),
        access_token=tokens["access_token"],
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Rotate refresh token and get a new access token",
)
async def refresh(
    response: Response, request: Request, db: AsyncSession = Depends(get_db)
):
    """Issue a new access + refresh token pair.

    Reads the refresh token from the httpOnly cookie (browser flow).
    Falls back to the JSON body for non-browser API clients.
    """
    token = request.cookies.get(REFRESH_TOKEN_COOKIE) or (await request.json()).get(
        "refresh_token"
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERR_REFRESH_TOKEN_REQUIRED,
        )

    tokens = await auth_service.refresh_tokens(db, refresh_token=token)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return AccessTokenResponse(access_token=tokens["access_token"])


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke the current refresh token",
)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token_cookie: str | None = Cookie(
        default=None,
        alias=REFRESH_TOKEN_COOKIE,
    ),
):
    """Revoke the refresh token and clear the cookie.

    Silently succeeds even if no valid token is present — there
    is nothing for the client to retry.
    """
    if refresh_token_cookie:
        await auth_service.logout(db, refresh_token=refresh_token_cookie)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out successfully")
