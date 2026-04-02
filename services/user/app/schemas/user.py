"""
Pydantic schemas for user profile endpoints.

Handles serialisation of User ORM objects into JSON responses
and validation of partial-update payloads (PATCH /users/me).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    role: RoleResponse
    is_active: bool
    is_banned: bool
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
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="New username",
    )
    email: EmailStr | None = Field(
        default=None,
        description="New email",
    )
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="New password",
    )
