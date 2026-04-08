"""Comment API routes.

Endpoints
---------
POST   /comments                      — create a comment or reply
GET    /comments                      — list comments
                                        ?thread_id=<uuid>       → top-level comments
                                        ?parent_comment_id=<uuid> → replies
PATCH  /comments/{comment_id}         — update a comment (author only)
DELETE /comments/{comment_id}         — soft-delete a comment
POST   /comments/{comment_id}/like    — like a comment
DELETE /comments/{comment_id}/like    — unlike a comment

Content masking
---------------
USER_DELETED comments have their ``content`` replaced with ``"[deleted]"``
in this route layer before serialisation so the schema stays simple.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.repositories import like_repo, user_snap_repo
from app.schemas.comment import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    CommentUpdate,
)
from app.schemas.common import MessageResponse
from app.schemas.like import LikeResponse
from app.schemas.user_snap import UserSnapResponse
from app.services import comment_service, like_service
from app.utils.constants import STATUS_MOD_REMOVED, STATUS_USER_DELETED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comments", tags=["Comments"])


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _enrich_comment(
    comment,
    db: AsyncSession,
    current_user: dict | None,
) -> CommentResponse:
    """Build a ``CommentResponse`` with author snap, ``is_liked``, and content
    masking applied for deleted comments.

    Masking rules:
      USER_DELETED → content="[deleted]", author anonymised.
      MOD_REMOVED  → content="[removed]", author anonymised.
                     (only reaches here for mod/admin callers)
      ACTIVE       → full content and author.
    """
    status_name = comment.status.name

    # Determine content masking and author visibility
    if status_name == STATUS_USER_DELETED:
        content = "[deleted]"
        author = None
    elif status_name == STATUS_MOD_REMOVED:
        content = "[removed]"
        author = None
    else:
        content = comment.content
        snap = await user_snap_repo.get_user_snap(db, comment.author_id)
        author = UserSnapResponse.model_validate(snap) if snap is not None else None

    is_liked = False
    if current_user is not None:
        is_liked = await like_repo.has_user_liked_comment(
            db,
            user_id=current_user["user_id"],
            comment_id=comment.id,
        )

    return CommentResponse(
        id=comment.id,
        thread_id=comment.thread_id,
        parent_comment_id=comment.parent_comment_id,
        author_id=comment.author_id,
        author=author,
        content=content,
        status=status_name,
        like_count=comment.like_count,
        reply_count=comment.reply_count,
        is_liked=is_liked,
        created_at=comment.created_at,
    )


async def _enrich_comments(
    comments: list,
    db: AsyncSession,
    current_user: dict | None,
) -> list[CommentResponse]:
    """Batch-enrich a list of comments with author snaps and ``is_liked``.

    Replaces the per-item ``_enrich_comment`` loop with:
      1. One ``WHERE user_id IN (…)`` for active-comment author snaps.
      2. One ``WHERE comment_id IN (…)`` for all like checks.
    """
    if not comments:
        return []

    # 1. Collect author IDs only for ACTIVE comments (deleted/removed are anonymised)
    active_author_ids = {
        c.author_id
        for c in comments
        if c.status.name not in (STATUS_USER_DELETED, STATUS_MOD_REMOVED)
    }
    snaps_map = await user_snap_repo.get_user_snaps_by_ids(db, active_author_ids)

    # 2. Batch-fetch liked comment IDs
    liked_ids: set = set()
    if current_user is not None:
        comment_ids = {c.id for c in comments}
        liked_ids = await like_repo.get_liked_comment_ids(
            db,
            user_id=current_user["user_id"],
            comment_ids=comment_ids,
        )

    # 3. Build responses from pre-fetched data
    results: list[CommentResponse] = []
    for comment in comments:
        status_name = comment.status.name

        if status_name == STATUS_USER_DELETED:
            content = "[deleted]"
            author = None
        elif status_name == STATUS_MOD_REMOVED:
            content = "[removed]"
            author = None
        else:
            content = comment.content
            snap = snaps_map.get(comment.author_id)
            author = UserSnapResponse.model_validate(snap) if snap is not None else None

        results.append(
            CommentResponse(
                id=comment.id,
                thread_id=comment.thread_id,
                parent_comment_id=comment.parent_comment_id,
                author_id=comment.author_id,
                author=author,
                content=content,
                status=status_name,
                like_count=comment.like_count,
                reply_count=comment.reply_count,
                is_liked=comment.id in liked_ids,
                created_at=comment.created_at,
            )
        )
    return results


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    payload: CommentCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Create a top-level comment or a reply.

    Set ``parent_comment_id`` to ``null`` for a top-level comment, or to
    an existing comment's UUID for a reply.
    """
    comment = await comment_service.create_comment(
        db,
        user_id=current_user["user_id"],
        thread_id=payload.thread_id,
        content=payload.content,
        parent_comment_id=payload.parent_comment_id,
    )
    return await _enrich_comment(comment, db, current_user)


@router.get("", response_model=CommentListResponse)
async def list_comments(
    thread_id: uuid.UUID | None = Query(
        default=None,
        description="Return top-level comments for this thread",
    ),
    parent_comment_id: uuid.UUID | None = Query(
        default=None,
        description="Return replies to this comment (overrides thread_id)",
    ),
    cursor: str | None = Query(default=None, description="ISO-8601 created_at cursor"),
    limit: int = Query(default=10, ge=1, le=100),
    current_user: dict | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentListResponse:
    """Paginated list of comments.

    Provide either ``thread_id`` (top-level comments, newest first) or
    ``parent_comment_id`` (replies, oldest first).  Exactly one must be
    given; 400 is returned when neither or both are supplied.
    """
    if parent_comment_id is None and thread_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'thread_id' or 'parent_comment_id'.",
        )
    if parent_comment_id is not None and thread_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide only one of 'thread_id' or 'parent_comment_id'.",
        )

    parsed_cursor: datetime | None = None
    if cursor is not None:
        try:
            parsed_cursor = datetime.fromisoformat(cursor)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid cursor format — expected ISO-8601 datetime.",
            )

    role = current_user["role"] if current_user is not None else None

    if parent_comment_id is not None:
        comments, pagination = await comment_service.get_replies(
            db,
            parent_comment_id=parent_comment_id,
            cursor=parsed_cursor,
            limit=limit,
            role=role,
        )
    else:
        comments, pagination = await comment_service.get_comments_for_thread(
            db,
            thread_id=thread_id,  # type: ignore[arg-type]
            cursor=parsed_cursor,
            limit=limit,
            role=role,
        )

    enriched = await _enrich_comments(comments, db, current_user)
    return CommentListResponse(comments=enriched, pagination=pagination)


@router.patch("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: uuid.UUID,
    payload: CommentUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Update a comment's content.  Only the author may update."""
    comment = await comment_service.update_comment(
        db,
        user_id=current_user["user_id"],
        comment_id=comment_id,
        content=payload.content,
    )
    return await _enrich_comment(comment, db, current_user)


@router.delete("/{comment_id}", response_model=MessageResponse)
async def delete_comment(
    comment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Soft-delete a comment.

    - Author     → status set to USER_DELETED (content shown as ``[deleted]``)
    - Mod/Admin  → status set to MOD_REMOVED  (comment hidden entirely)
    - Anyone else → 403
    """
    await comment_service.delete_comment(
        db,
        user_id=current_user["user_id"],
        role=current_user["role"],
        comment_id=comment_id,
    )
    return MessageResponse(message="Comment deleted successfully.")


@router.post(
    "/{comment_id}/like",
    response_model=LikeResponse,
    status_code=status.HTTP_200_OK,
)
async def like_comment(
    comment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LikeResponse:
    """Like a comment.  Raises 409 if the user already liked it."""
    return await like_service.like_comment(
        db,
        user_id=current_user["user_id"],
        comment_id=comment_id,
    )


@router.delete(
    "/{comment_id}/like",
    response_model=LikeResponse,
    status_code=status.HTTP_200_OK,
)
async def unlike_comment(
    comment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LikeResponse:
    """Unlike a comment.  Raises 409 if the user has not liked it."""
    return await like_service.unlike_comment(
        db,
        user_id=current_user["user_id"],
        comment_id=comment_id,
    )
