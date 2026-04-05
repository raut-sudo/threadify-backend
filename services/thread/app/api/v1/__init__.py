"""v1 API router — aggregates all versioned endpoint groups.

Mounted at ``/api/v1`` in ``main.py``.

Route prefixes and tags
-----------------------
  /threads      — thread CRUD + thread likes
  /comments     — comment CRUD + comment likes
  /user-snaps   — temporary user snapshot testing endpoints
"""

from fastapi import APIRouter

from app.api.v1.comments import router as comments_router
from app.api.v1.threads import router as threads_router
from app.api.v1.user_snaps import router as user_snaps_router

router = APIRouter()
router.include_router(threads_router)
router.include_router(comments_router)
router.include_router(user_snaps_router)
