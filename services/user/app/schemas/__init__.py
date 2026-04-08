"""
schemas package — re-exports all Pydantic schemas for convenient imports.

Usage:
    from app.schemas import RegisterRequest, UserResponse, ...
"""

from app.schemas.auth import (
    AccessTokenResponse,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.schemas.user import (
    RoleResponse,
    RoleUpdateRequest,
    UserListResponse,
    UserResponse,
    UserUpdate,
)

__all__ = [
    "AccessTokenResponse",
    "AuthResponse",
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "TokenRefreshRequest",
    "RoleResponse",
    "RoleUpdateRequest",
    "UserResponse",
    "UserListResponse",
    "UserUpdate",
    "MessageResponse",
]
