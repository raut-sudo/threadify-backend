"""Thread service — business logic for thread lifecycle operations.

Orchestrates thread_repo calls, enforces authorization, and applies
the deletion visibility rules:

  ACTIVE       → visible to everyone, content shown normally
  USER_DELETED → visible to everyone, title/content masked as [deleted]
                 in the route layer.  Comments remain accessible.
  MOD_REMOVED  → hidden from regular users (returns 404).
                 Visible to mods/admins for auditing.

Every public function receives an ``AsyncSession`` and raises a domain
``AppException`` on any failure, keeping route handlers thin.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotAuthorizedError,
    ThreadNotFoundError,
)
from app.events import publisher
from app.events.payloads import (
    build_mention_notification,
    build_thread_created,
    build_thread_deleted,
    build_thread_updated,
)
from app.repositories import tag_repo, thread_repo, user_snap_repo
from app.repositories.seed import get_entity_status_by_name
from app.schemas.common import CursorPaginationMeta
from app.utils.constants import (
    DEFAULT_CURSOR_LIMIT,
    ROLE_ADMIN,
    ROLE_MODERATOR,
    STATUS_ACTIVE,
    STATUS_MOD_REMOVED,
    STATUS_USER_DELETED,
)
from app.utils.mentions import extract_mentions

logger = logging.getLogger(__name__)


# ── Private helpers ───────────────────────────────────────────────────────────


def _is_privileged(role: str) -> bool:
    """Return True for ADMIN or MODERATOR roles."""
    return role in (ROLE_ADMIN, ROLE_MODERATOR)


def _build_cursor_meta(items: list, limit: int) -> CursorPaginationMeta:
    """Build pagination metadata from a page of results.

    If the page is full (len == limit), there may be more items and
    ``next_cursor`` is set to the ``created_at`` ISO string of the last
    item for the client to use on the next request.
    """
    has_more = len(items) == limit
    next_cursor = items[-1].created_at.isoformat() if has_more and items else None
    return CursorPaginationMeta(next_cursor=next_cursor, has_more=has_more)


async def _require_status_id(db: AsyncSession, name: str) -> uuid.UUID:
    """Resolve an entity status name to its UUID. Raises 500 if missing."""
    status = await get_entity_status_by_name(db, name)
    if status is None:
        # This should never happen after startup seed — indicates a DB issue.
        raise RuntimeError(f"Required entity status '{name}' not found in DB.")
    return status.id


# ── Public service functions ──────────────────────────────────────────────────


async def create_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str,
    content: str,
    tag_names: list[str] | None = None,
) -> object:
    """Create a new thread owned by ``user_id``.

    New threads are created with ACTIVE status.  If ``tag_names`` are
    provided, they are normalised to lowercase and associated with the
    thread via the join table.
    Returns the persisted Thread ORM instance.
    """
    status_id = await _require_status_id(db, STATUS_ACTIVE)
    thread = await thread_repo.create_thread(
        db,
        author_id=user_id,
        title=title,
        content=content,
        status_id=status_id,
    )

    if tag_names:
        tags = await tag_repo.get_or_create_tags(db, tag_names)
        await db.refresh(thread, attribute_names=["tags"])
        thread.tags = tags
        await db.flush()

    # Eagerly load tags so _enrich_thread can access them synchronously.
    # selectin lazy loading doesn't fire on freshly created objects.
    await db.refresh(thread, attribute_names=["tags"])

    logger.info("Thread created by user=%s thread=%s", user_id, thread.id)

    snap = await user_snap_repo.get_user_snap(db, user_id)
    await publisher.publish_realtime(
        "realtime.post",
        build_thread_created(
            thread_id=thread.id,
            title=thread.title,
            author_id=user_id,
            author_username=snap.username if snap else None,
            author_avatar_url=snap.avatar_url if snap else None,
            created_at=thread.created_at,
        ),
    )

    # @mention notifications
    mentioned = extract_mentions(content)
    if mentioned:
        resolved = await user_snap_repo.get_user_ids_by_usernames(
            db,
            mentioned,
        )
        if resolved:
            event = build_mention_notification(
                actor_id=user_id,
                actor_username=snap.username if snap else None,
                target_user_ids=list(resolved.values()),
                entity_type="THREAD",
                entity_id=thread.id,
                thread_id=thread.id,
                content_preview=title,
            )
            if event:
                await publisher.publish(
                    "notification.mentioned",
                    event,
                )

    return thread


async def update_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    title: str | None = None,
    content: str | None = None,
    tag_names: list[str] | None = None,
) -> object:
    """Update a thread's title, content, and/or tags.

    Only the thread author may update. Raises ``NotAuthorizedError`` if
    the requesting user is not the author (mods cannot edit others' content).
    """
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None:
        raise ThreadNotFoundError()

    if thread.author_id != user_id:
        raise NotAuthorizedError()

    updated = await thread_repo.update_thread(db, thread, title=title, content=content)

    if tag_names is not None:
        tags = await tag_repo.get_or_create_tags(db, tag_names)
        await db.refresh(updated, attribute_names=["tags"])
        updated.tags = tags
        await db.flush()
        await db.refresh(updated, attribute_names=["tags"])

    await publisher.publish_realtime(
        "realtime.thread.updated",
        build_thread_updated(
            thread_id=updated.id,
            title=updated.title,
            content=updated.content,
            tags=[t.name for t in updated.tags],
            updated_at=updated.updated_at,
        ),
    )

    return updated


async def delete_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    role: str,
    thread_id: uuid.UUID,
) -> object:
    """Soft-delete a thread with the appropriate status.

    - Author     → USER_DELETED  (visible, title/content masked as [deleted])
    - Mod/Admin  → MOD_REMOVED   (hidden from regular users, visible to mods)
    - Anyone else → NotAuthorizedError
    """
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None:
        raise ThreadNotFoundError()

    if _is_privileged(role):
        status_name = STATUS_MOD_REMOVED
    elif thread.author_id == user_id:
        status_name = STATUS_USER_DELETED
    else:
        raise NotAuthorizedError()

    status_id = await _require_status_id(db, status_name)
    result = await thread_repo.soft_delete_thread(
        db,
        thread,
        status_id=status_id,
    )

    await publisher.publish_realtime(
        "realtime.thread.deleted",
        build_thread_deleted(
            thread_id=thread_id,
            status=status_name,
        ),
    )

    return result


async def get_thread(
    db: AsyncSession,
    *,
    thread_id: uuid.UUID,
    role: str | None = None,
) -> object:
    """Fetch a thread, enforcing visibility rules.

    - ACTIVE       → returned normally
    - USER_DELETED → returned as-is (route layer masks title/content)
    - MOD_REMOVED + non-privileged → ``ThreadNotFoundError`` (404)
    - MOD_REMOVED + mod/admin      → returned as-is (for auditing)
    """
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None:
        raise ThreadNotFoundError()

    status_name = thread.status.name

    if status_name == STATUS_ACTIVE:
        return thread

    if status_name == STATUS_USER_DELETED:
        # Visible to everyone — route layer masks title/content as [deleted].
        # Comments on this thread remain accessible.
        return thread

    if status_name == STATUS_MOD_REMOVED:
        # Only mods/admins can view for auditing purposes.
        if _is_privileged(role or ""):
            return thread
        raise ThreadNotFoundError()

    # Unknown status — treat as not found
    raise ThreadNotFoundError()


async def list_threads(
    db: AsyncSession,
    *,
    cursor: datetime | None = None,
    limit: int = DEFAULT_CURSOR_LIMIT,
    search: str | None = None,
    tag: str | None = None,
) -> tuple[list, CursorPaginationMeta]:
    """Return a cursor-paginated page of ACTIVE threads with pagination meta.

    ``cursor`` is the ``created_at`` datetime of the last item from the
    previous page.  Pass ``None`` for the first page.
    ``search`` triggers PostgreSQL full-text search on title + content.
    ``tag`` filters by exact tag name (lowercased).
    """
    limit = min(limit, 100)  # guard against unreasonably large requests
    threads = await thread_repo.list_threads(
        db,
        cursor=cursor,
        limit=limit,
        search=search,
        tag=tag,
    )
    meta = _build_cursor_meta(threads, limit)
    return threads, meta
