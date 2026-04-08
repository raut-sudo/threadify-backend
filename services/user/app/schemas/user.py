"""
Pydantic schemas for user profile endpoints.

Handles serialisation of User ORM objects into JSON responses
and validation of partial-update payloads (PATCH /users/me).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.utils.constants import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    USERNAME_PATTERN,
)


class RoleResponse(BaseModel):
    """Nested role object embedded inside UserResponse.

    Mirrors the roles DB table so clients can display the
    role name and description without a separate API call.
    """

    id: uuid.UUID
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """Public user profile returned by GET /users/me and admin routes.

    Uses 'from_attributes' so it can be constructed directly from
    an ORM User instance with an eagerly-loaded role relationship.
    """

    id: uuid.UUID
    username: str
    email: EmailStr
    avatar_url: str | None = None
    bio: str | None = None
    role: RoleResponse
    deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Partial-update payload for PATCH /users/me.

    Every field is optional — only the fields the client sends
    will be applied. Validation rules mirror RegisterRequest.
    """

    username: str | None = Field(
        default=None,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        pattern=USERNAME_PATTERN,
        description="New username",
    )
    email: EmailStr | None = Field(
        default=None,
        description="New email",
    )
    password: str | None = Field(
        default=None,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="New password",
    )
    bio: str | None = Field(
        default=None,
        max_length=500,
        description="Short bio (max 500 chars)",
    )
    avatar_url: str | None = Field(
        default=None,
        max_length=512,
        description="Cloudinary avatar URL (upload via client-side unsigned upload, then send URL here)",
    )


class UserListResponse(BaseModel):
    """Paginated list of users returned by GET /users/."""

    users: list[UserResponse]
    total: int


class RoleUpdateRequest(BaseModel):
    """Admin payload for changing a user's role.

    Only MEMBER and MOD are allowed — admin promotion is blocked.
    """

    role: str = Field(
        ...,
        pattern=r"^(MEMBER|MOD)$",
        description="Target role (MEMBER or MOD)",
        examples=["MOD"],
    )
