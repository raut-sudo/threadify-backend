"""Event payload schemas and builder functions.

Each builder returns a typed Pydantic model (or None for suppressed events)
that the publisher serialises to JSON.  Having typed models here gives the
notification service a shared contract to validate against.
"""

from uuid import UUID

from pydantic import BaseModel

# ── Schemas ───────────────────────────────────────────────────────────────────


class CommentCreatedEvent(BaseModel):
    event_type: str
    actor_id: str
    actor_username: str | None
    target_user_ids: list[str]
    entity: dict
    metadata: dict


# ── Builders ──────────────────────────────────────────────────────────────────


def build_comment_created(
    *,
    actor_id: UUID,
    actor_username: str | None,
    post_owner_id: UUID,
    post_id: UUID,
    comment_id: UUID,
) -> CommentCreatedEvent | None:
    """Build a CommentCreatedEvent payload.

    Returns None when actor_id == post_owner_id (self-comment suppression).
    The caller should check for None before publishing.
    """
    if actor_id == post_owner_id:
        return None

    return CommentCreatedEvent(
        event_type="COMMENT_CREATED",
        actor_id=str(actor_id),
        actor_username=actor_username,
        target_user_ids=[str(post_owner_id)],
        entity={"type": "THREAD", "id": str(post_id)},
        metadata={"comment_id": str(comment_id)},
    )
