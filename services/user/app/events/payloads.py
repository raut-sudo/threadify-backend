"""Event payload schemas for the user service.

These are published to the ``user_exchange`` topic exchange so downstream
services (thread, notification, etc.) can keep their local caches in sync.

Routing keys
------------
  user.registered — emitted once after a new account is created
  user.updated    — emitted when username or avatar_url changes
"""

from pydantic import BaseModel


class UserSnapEvent(BaseModel):
    """Payload carried by both ``user.registered`` and ``user.updated`` events.

    Downstream consumers use this to upsert their local ``UserSnap`` row.
    """

    event_type: str  # "user.registered" | "user.updated"
    user_id: str  # UUID as string for JSON portability
    username: str
    avatar_url: str | None = None
