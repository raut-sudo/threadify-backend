"""models package — re-exports all ORM models for convenient imports.

Import order matters for SQLAlchemy's mapper configuration:
  1. EntityStatus  — no FK deps
  2. UserSnap      — no FK deps
  3. Thread        — depends on EntityStatus
  4. Comment       — depends on EntityStatus + Thread (self-referential)
  5. ThreadLike    — depends on Thread
  6. CommentLike   — depends on Comment

Usage::

    from app.models import EntityStatus, Thread, Comment
    from app.models import ThreadLike, CommentLike, UserSnap
"""

from app.models.comment import Comment
from app.models.comment_like import CommentLike
from app.models.entity_status import EntityStatus
from app.models.thread import Thread
from app.models.thread_like import ThreadLike
from app.models.user_snap import UserSnap

__all__ = [
    "EntityStatus",
    "UserSnap",
    "Thread",
    "Comment",
    "ThreadLike",
    "CommentLike",
]
