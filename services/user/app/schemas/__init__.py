"""
schemas package — re-exports all Pydantic schemas for convenient imports.

Usage:
    from app.schemas import RegisterRequest, UserResponse, ...
"""

from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.schemas.user import RoleResponse, UserResponse, UserUpdate

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "TokenRefreshRequest",
    "RoleResponse",
    "UserResponse",
    "UserUpdate",
    "MessageResponse",
]
