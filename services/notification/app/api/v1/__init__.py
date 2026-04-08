"""v1 API router — aggregates all versioned endpoint groups.

Mounted at ``/api/v1`` in ``main.py``.
"""

from fastapi import APIRouter

from app.api.v1.notifications import router as notifications_router

router = APIRouter()
router.include_router(notifications_router)
