"""
Pydantic schemas for authentication endpoints.

Covers registration, login, and token refresh request/response bodies.
All inbound payloads are validated here before reaching the service layer.
"""

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserResponse
from app.utils.constants import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    TOKEN_TYPE_BEARER,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    USERNAME_PATTERN,
)


class RegisterRequest(BaseModel):
    """Inbound payload for POST /auth/register.

    Validates username format (alphanumeric + underscores), email
    structure via EmailStr, and password length constraints.
    """

    username: str = Field(
        ...,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        pattern=USERNAME_PATTERN,
        examples=["john_doe"],
        description="Alphanumeric username (3-50 chars, underscores allowed)",
    )
    email: EmailStr = Field(
        ...,
        examples=["john@example.com"],
        description="Valid email address",
    )
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        examples=["Str0ngP@ss!"],
        description="Password (8-128 characters)",
    )
    bio: str | None = Field(
        default=None,
        max_length=500,
        examples=["Full-stack dev from Mumbai"],
        description="Short bio (max 500 chars, optional)",
    )
    avatar_url: str | None = Field(
        default=None,
        max_length=512,
        examples=["https://res.cloudinary.com/..."],
        description="Cloudinary avatar URL (upload via PATCH /users/me/avatar first)",
    )


class LoginRequest(BaseModel):
    """Inbound payload for POST /auth/login.

    Only requires username and password — the service layer handles
    credential verification and token issuance.
    """

    username: str = Field(
        ...,
        examples=["john_doe"],
        description="Username",
    )
    password: str = Field(
        ...,
        examples=["Str0ngP@ss!"],
        description="Password",
    )


class TokenResponse(BaseModel):
    """Returned after successful login, registration, or token refresh.

    Contains the short-lived JWT access token and an opaque refresh
    token for obtaining new access tokens without re-authenticating.
    """

    access_token: str
    refresh_token: str
    token_type: str = TOKEN_TYPE_BEARER


class TokenRefreshRequest(BaseModel):
    """Inbound payload for POST /auth/refresh.

    The client sends the opaque refresh token it received at login;
    the server validates it via DB lookup and issues a new token pair.
    """

    refresh_token: str = Field(
        ...,
        description="Opaque refresh token issued at login",
    )


class AccessTokenResponse(BaseModel):
    """Returned by the /refresh endpoint.

    Contains only the short-lived JWT — the new refresh token is
    transported via an httpOnly cookie, not in the response body.
    """

    access_token: str
    token_type: str = TOKEN_TYPE_BEARER


class AuthResponse(BaseModel):
    """Returned by /signup and /login.

    Combines the user profile with the access token so the client
    gets everything it needs in a single round-trip.  The refresh
    token is set as an httpOnly cookie.
    """

    user: UserResponse
    access_token: str
    token_type: str = TOKEN_TYPE_BEARER


class ChangePasswordRequest(BaseModel):
    """Payload for PUT /users/me/password."""

    current_password: str = Field(
        ...,
        min_length=1,
        examples=["OldP@ss123"],
    )
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        examples=["NewStr0ng!"],
    )
