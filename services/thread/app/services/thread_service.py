"""Thread service — business logic for thread lifecycle operations.

Orchestrates thread_repo calls, enforces authorization, and applies
the deletion visibility rules defined in the LLD (§9):

  ACTIVE       → visible to everyone, content shown normally
  USER_DELETED → accessible via direct link, content intact (feed excluded)
  MOD_REMOVED  → hidden from all non-privileged users (returns 404)

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
from app.repositories import thread_repo
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
) -> object:
    """Create a new thread owned by ``user_id``.

    New threads are created with ACTIVE status.
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
    logger.info("Thread created by user=%s thread=%s", user_id, thread.id)
    return thread


async def update_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    title: str | None = None,
    content: str | None = None,
) -> object:
    """Update a thread's title and/or content.

    Only the thread author may update. Raises ``NotAuthorizedError`` if
    the requesting user is not the author (mods cannot edit others' content).
    """
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None:
        raise ThreadNotFoundError()

    if thread.author_id != user_id:
        raise NotAuthorizedError()

    return await thread_repo.update_thread(db, thread, title=title, content=content)


async def delete_thread(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    role: str,
    thread_id: uuid.UUID,
) -> object:
    """Soft-delete a thread with the appropriate status.

    - Author     → USER_DELETED  (visible with "[deleted]" placeholder)
    - Mod/Admin  → MOD_REMOVED   (hidden from everyone except mods/admins)
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
    return await thread_repo.soft_delete_thread(db, thread, status_id=status_id)


async def get_thread(
    db: AsyncSession,
    *,
    thread_id: uuid.UUID,
    role: str | None = None,
) -> object:
    """Fetch a thread, enforcing visibility rules.

    - MOD_REMOVED + non-privileged caller → ``ThreadNotFoundError`` (404)
    - MOD_REMOVED + mod/admin caller      → returned as-is
    - USER_DELETED                         → returned as-is (route applies masking)
    - ACTIVE                               → returned normally
    """
    thread = await thread_repo.get_thread_by_id(db, thread_id)
    if thread is None:
        raise ThreadNotFoundError()

    if thread.status.name == STATUS_MOD_REMOVED and not _is_privileged(role or ""):
        raise ThreadNotFoundError()

    return thread


async def list_threads(
    db: AsyncSession,
    *,
    cursor: datetime | None = None,
    limit: int = DEFAULT_CURSOR_LIMIT,
) -> tuple[list, CursorPaginationMeta]:
    """Return a cursor-paginated page of ACTIVE threads with pagination meta.

    ``cursor`` is the ``created_at`` datetime of the last item from the
    previous page.  Pass ``None`` for the first page.
    """
    limit = min(limit, 100)  # guard against unreasonably large requests
    threads = await thread_repo.list_threads(db, cursor=cursor, limit=limit)
    meta = _build_cursor_meta(threads, limit)
    return threads, meta
