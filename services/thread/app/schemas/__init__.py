"""schemas package — re-exports all Pydantic schemas for convenient imports.

Usage::

    from app.schemas import ThreadCreate, ThreadResponse
    from app.schemas import CommentCreate, CommentResponse
    from app.schemas import LikeResponse, UserSnapResponse
"""

from app.schemas.comment import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    CommentUpdate,
)
from app.schemas.common import CursorPaginationMeta, MessageResponse
from app.schemas.like import LikeResponse
from app.schemas.thread import (
    ThreadCreate,
    ThreadListResponse,
    ThreadResponse,
    ThreadUpdate,
)
from app.schemas.user_snap import UserSnapCreate, UserSnapResponse, UserSnapUpdate

__all__ = [
    # common
    "MessageResponse",
    "CursorPaginationMeta",
    # thread
    "ThreadCreate",
    "ThreadUpdate",
    "ThreadResponse",
    "ThreadListResponse",
    # comment
    "CommentCreate",
    "CommentUpdate",
    "CommentResponse",
    "CommentListResponse",
    # like
    "LikeResponse",
    # user snap
    "UserSnapCreate",
    "UserSnapUpdate",
    "UserSnapResponse",
]
