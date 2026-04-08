"""
Shared / generic Pydantic schemas used across endpoints.

Houses simple response wrappers that don't belong to any
specific domain (auth, user profile, etc.).
"""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic single-message response for confirmations and errors.

    Used by endpoints that return a plain status message rather
    than a structured domain object (e.g. logout, account deletion).
    """

    message: str
