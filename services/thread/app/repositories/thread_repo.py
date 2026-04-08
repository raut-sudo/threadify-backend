"""Repository layer for Thread database operations.

Pure data-access — no business logic, no HTTP concerns.  Every function
receives an ``AsyncSession`` and returns ORM model instances or ``None``.
The service layer is responsible for authorization and orchestration.

Cursor-based pagination
-----------------------
The ``list_threads`` function uses ``created_at`` as the cursor.  Clients
pass the ``created_at`` value of the last item they received; the next
page returns rows strictly older than that timestamp.  This avoids the
"offset drift" problem where new inserts shift rows between pages.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.entity_status import EntityStatus
from app.models.tag import Tag, thread_tags
from app.models.thread import Thread

logger = logging.getLogger(__name__)


async def create_thread(
    db: AsyncSession,
    *,
    author_id: uuid.UUID,
    title: str,
    content: str,
    status_id: uuid.UUID,
) -> Thread:
    """Insert a new thread row and return the persisted instance."""
    thread = Thread(
        author_id=author_id,
        title=title,
        content=content,
        status_id=status_id,
    )
    db.add(thread)
    await db.flush()
    await db.refresh(thread, attribute_names=["status"])
    logger.info("Thread created: id=%s author=%s", thread.id, author_id)
    return thread


async def get_thread_by_id(
    db: AsyncSession,
    thread_id: uuid.UUID,
) -> Thread | None:
    """Fetch a thread by primary key with its status relationship loaded.

    Returns ``None`` if no thread matches the given UUID.
    """
    stmt = (
        select(Thread).options(joinedload(Thread.status)).where(Thread.id == thread_id)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def list_threads(
    db: AsyncSession,
    *,
    cursor: datetime | None = None,
    limit: int = 10,
    search: str | None = None,
    tag: str | None = None,
) -> list[Thread]:
    """Return a cursor-paginated page of ACTIVE threads, newest first.

    Only ``ACTIVE`` threads are included — ``USER_DELETED`` and
    ``MOD_REMOVED`` threads are excluded from the public feed.

    Filters:
        search — PostgreSQL full-text search on title (weight A) and
                 content (weight B) via the ``search_vector`` tsvector column.
        tag    — exact match on a tag name (lowercased).  Threads must
                 be associated with the tag via the ``thread_tags`` table.

    ``cursor`` — if provided, returns only threads created *before*
    this timestamp (exclusive), enabling stable forward pagination.
    """
    stmt = (
        select(Thread)
        .join(EntityStatus, Thread.status_id == EntityStatus.id)
        .options(joinedload(Thread.status))
        .where(EntityStatus.name == "ACTIVE")
        .order_by(Thread.created_at.desc())
        .limit(limit)
    )

    if cursor is not None:
        stmt = stmt.where(Thread.created_at < cursor)

    if search is not None:
        search = search.strip()
        if search:
            # Build a prefix-aware tsquery: each word gets a :* suffix so
            # partial typing works (e.g. "pro" matches "programming").
            # Words are ANDed together.  Falls back to ILIKE on title+content
            # when the tsquery is empty (very short / stop-word-only input).
            words = search.split()
            ts_terms = " & ".join(f"{w.replace(chr(39), '')}:*" for w in words if w)
            if ts_terms:
                ts_query = func.to_tsquery("english", ts_terms)
                ilike_pattern = f"%{search}%"
                stmt = stmt.where(
                    or_(
                        Thread.search_vector.op("@@")(ts_query),
                        Thread.title.ilike(ilike_pattern),
                        Thread.content.ilike(ilike_pattern),
                    )
                )

    if tag is not None:
        stmt = (
            stmt.join(thread_tags, Thread.id == thread_tags.c.thread_id)
            .join(Tag, thread_tags.c.tag_id == Tag.id)
            .where(Tag.name == tag.lower().strip())
        )

    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def update_thread(
    db: AsyncSession,
    thread: Thread,
    **fields: object,
) -> Thread:
    """Apply a partial update to an existing thread.

    Only non-``None`` values in ``fields`` are written, implementing
    COALESCE-style semantics — unset fields retain their current value.
    """
    for key, value in fields.items():
        if value is not None:
            setattr(thread, key, value)

    thread.updated_at = datetime.now(UTC)
    await db.flush()
    logger.debug("Thread updated: id=%s fields=%s", thread.id, list(fields.keys()))
    return thread


async def soft_delete_thread(
    db: AsyncSession,
    thread: Thread,
    *,
    status_id: uuid.UUID,
) -> Thread:
    """Soft-delete a thread by updating its status and recording deleted_at.

    The row is never removed — callers pass the appropriate ``status_id``
    (USER_DELETED or MOD_REMOVED) from the seeded ``entity_status`` table.
    """
    thread.status_id = status_id
    thread.deleted_at = datetime.now(UTC)
    thread.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(thread, attribute_names=["status"])
    logger.info("Thread soft-deleted: id=%s status_id=%s", thread.id, status_id)
    return thread


async def increment_comment_count(db: AsyncSession, thread_id: uuid.UUID) -> None:
    """Atomically increment the denormalized comment counter by 1."""
    stmt = (
        update(Thread)
        .where(Thread.id == thread_id)
        .values(comment_count=Thread.comment_count + 1)
    )
    await db.execute(stmt)


async def decrement_comment_count(db: AsyncSession, thread_id: uuid.UUID) -> None:
    """Atomically decrement the denormalized comment counter by 1 (floor 0)."""
    stmt = (
        update(Thread)
        .where(Thread.id == thread_id)
        .values(comment_count=func.greatest(0, Thread.comment_count - 1))
    )
    await db.execute(stmt)
