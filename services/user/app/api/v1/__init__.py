"""
v1 API router — aggregates all versioned endpoint groups.

Mounted at ``/api/v1`` in main.py.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
