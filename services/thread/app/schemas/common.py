"""Shared / generic Pydantic schemas used across thread service endpoints.

Houses simple response wrappers and pagination metadata that don't
belong to any specific domain (threads, comments, likes, etc.).
"""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic single-message response for confirmations.

    Used by endpoints that return a plain status message rather than
    a structured domain object (e.g. delete confirmations).
    """

    message: str


class CursorPaginationMeta(BaseModel):
    """Metadata for cursor-based paginated list responses.

    ``next_cursor`` is an ISO-8601 timestamp string clients pass back
    as ``?cursor=`` on the next request.  ``None`` means no more pages.
    ``has_more`` is a convenience flag so clients don't need to check
    whether ``next_cursor`` is null.
    """

    next_cursor: str | None = None
    has_more: bool
