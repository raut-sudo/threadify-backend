"""Thread API routes.

Endpoints
---------
POST   /threads                    — create a thread
GET    /threads                    — paginated list of ACTIVE threads
GET    /threads/{thread_id}        — get a single thread
PATCH  /threads/{thread_id}        — update a thread (author only)
DELETE /threads/{thread_id}        — soft-delete a thread
POST   /threads/{thread_id}/like   — like a thread
DELETE /threads/{thread_id}/like   — unlike a thread
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.repositories import like_repo, user_snap_repo
from app.schemas.common import MessageResponse
from app.schemas.like import LikeResponse
from app.schemas.thread import (
    ThreadCreate,
    ThreadListResponse,
    ThreadResponse,
    ThreadUpdate,
)
from app.schemas.user_snap import UserSnapResponse
from app.services import like_service, thread_service
from app.utils.constants import STATUS_USER_DELETED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads", tags=["Threads"])


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _enrich_thread(
    thread,
    db: AsyncSession,
    current_user: dict | None,
) -> ThreadResponse:
    """Build a ``ThreadResponse`` with author snap and ``is_liked`` populated.

    For USER_DELETED threads, title and content are masked as ``[deleted]``.
    The thread remains accessible so its comment tree is still reachable.
    """
    snap = await user_snap_repo.get_user_snap(db, thread.author_id)
    author = UserSnapResponse.model_validate(snap) if snap is not None else None

    is_liked = False
    if current_user is not None:
        is_liked = await like_repo.has_user_liked_thread(
            db,
            user_id=current_user["user_id"],
            thread_id=thread.id,
        )

    # Mask title and content for author-deleted threads
    status_name = thread.status.name
    if status_name == STATUS_USER_DELETED:
        title = "[deleted]"
        content = "[deleted]"
    else:
        title = thread.title
        content = thread.content

    return ThreadResponse(
        id=thread.id,
        title=title,
        content=content,
        author_id=thread.author_id,
        author=author,
        status=status_name,
        like_count=thread.like_count,
        comment_count=thread.comment_count,
        is_liked=is_liked,
        tags=[tag.name for tag in thread.tags],
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    payload: ThreadCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    """Create a new thread owned by the authenticated user."""
    thread = await thread_service.create_thread(
        db,
        user_id=current_user["user_id"],
        title=payload.title,
        content=payload.content,
        tag_names=payload.tags,
    )
    return await _enrich_thread(thread, db, current_user)


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    cursor: str | None = Query(default=None, description="ISO-8601 created_at cursor"),
    limit: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
        description="Full-text search on title and content",
    ),
    tag: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
        description="Exact tag name filter (case-insensitive)",
    ),
    current_user: dict | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadListResponse:
    """Return a cursor-paginated list of ACTIVE threads, newest first.

    Supports full-text search via ``?search=<text>`` and exact tag
    filtering via ``?tag=<name>``.  Both can be combined.
    """
    parsed_cursor: datetime | None = None
    if cursor is not None:
        parsed_cursor = datetime.fromisoformat(cursor)

    threads, pagination = await thread_service.list_threads(
        db,
        cursor=parsed_cursor,
        limit=limit,
        search=search,
        tag=tag,
    )

    enriched = [await _enrich_thread(t, db, current_user) for t in threads]
    return ThreadListResponse(threads=enriched, pagination=pagination)


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: uuid.UUID,
    current_user: dict | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    """Fetch a single thread by ID.

    Returns 404 for MOD_REMOVED threads when the requester is not
    a mod/admin.  USER_DELETED threads are returned with title and
    content masked as ``[deleted]``.  Comments remain accessible.
    """
    role = current_user["role"] if current_user is not None else None
    thread = await thread_service.get_thread(db, thread_id=thread_id, role=role)
    return await _enrich_thread(thread, db, current_user)


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: uuid.UUID,
    payload: ThreadUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    """Partially update a thread's title and/or content.

    Only the thread author may update.  Raises 403 for anyone else.
    """
    thread = await thread_service.update_thread(
        db,
        user_id=current_user["user_id"],
        thread_id=thread_id,
        title=payload.title,
        content=payload.content,
        tag_names=payload.tags,
    )
    return await _enrich_thread(thread, db, current_user)


@router.delete("/{thread_id}", response_model=MessageResponse)
async def delete_thread(
    thread_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Soft-delete a thread.

    - Author     → status set to USER_DELETED
    - Mod/Admin  → status set to MOD_REMOVED
    - Anyone else → 403
    """
    await thread_service.delete_thread(
        db,
        user_id=current_user["user_id"],
        role=current_user["role"],
        thread_id=thread_id,
    )
    return MessageResponse(message="Thread deleted successfully.")


@router.post(
    "/{thread_id}/like",
    response_model=LikeResponse,
    status_code=status.HTTP_200_OK,
)
async def like_thread(
    thread_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LikeResponse:
    """Like a thread.  Raises 409 if the user already liked it."""
    return await like_service.like_thread(
        db,
        user_id=current_user["user_id"],
        thread_id=thread_id,
    )


@router.delete(
    "/{thread_id}/like",
    response_model=LikeResponse,
    status_code=status.HTTP_200_OK,
)
async def unlike_thread(
    thread_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LikeResponse:
    """Unlike a thread.  Raises 409 if the user has not liked it."""
    return await like_service.unlike_thread(
        db,
        user_id=current_user["user_id"],
        thread_id=thread_id,
    )
