"""Pydantic schemas for the like / unlike endpoints.

A single ``LikeResponse`` is returned by both thread-like and
comment-like endpoints so the client always knows the new count
and whether the current user has liked the entity.
"""

from pydantic import BaseModel


class LikeResponse(BaseModel):
    """Returned by POST/DELETE /{threads|comments}/{id}/like.

    ``like_count`` — updated denormalized count after the operation.
    ``liked``      — ``True`` if the current user now likes the entity,
                     ``False`` if they just unliked it.
    """

    like_count: int
    liked: bool
