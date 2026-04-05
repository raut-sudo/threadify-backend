"""repositories package — re-exports seed and all repo modules.

Usage::

    from app.repositories import thread_repo, comment_repo
    from app.repositories import like_repo, user_snap_repo
    from app.repositories.seed import seed_entity_statuses
"""

from app.repositories import (
    comment_repo,
    like_repo,
    thread_repo,
    user_snap_repo,
)
from app.repositories.seed import seed_entity_statuses

__all__ = [
    "thread_repo",
    "comment_repo",
    "like_repo",
    "user_snap_repo",
    "seed_entity_statuses",
]
