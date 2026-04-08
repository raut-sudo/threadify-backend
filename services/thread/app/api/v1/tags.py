"""Tags API — public endpoint for tag discovery / autocomplete.

Provides a lightweight listing of existing tag names so the frontend
can offer suggestions while the user types.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories import tag_repo

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get(
    "/",
    response_model=list[str],
    summary="List available tags",
)
async def list_tags(
    search: str | None = Query(default=None, description="Substring filter"),
    limit: int = Query(default=50, ge=1, le=100, description="Max tags to return"),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return tag names, optionally filtered by a search substring.

    Used by the frontend for tag autocomplete / suggestions.
    """
    return await tag_repo.list_tags(db, search=search, limit=limit)
