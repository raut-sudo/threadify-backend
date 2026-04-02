"""
Pydantic schemas for authentication endpoints.

Covers registration, login, and token refresh request/response bodies.
All inbound payloads are validated here before reaching the service layer.
"""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Inbound payload for POST /auth/register.

    Validates username format (alphanumeric + underscores), email
    structure via EmailStr, and password length constraints.
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
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
        min_length=8,
        max_length=128,
        examples=["Str0ngP@ss!"],
        description="Password (8-128 characters)",
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
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    """Inbound payload for POST /auth/refresh.

    The client sends the opaque refresh token it received at login;
    the server validates it via DB lookup and issues a new token pair.
    """

    refresh_token: str = Field(
        ...,
        description="Opaque refresh token issued at login",
    )
