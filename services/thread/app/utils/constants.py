"""Centralised constants for the thread service.

Keeps all magic strings and numbers in one place so they stay
consistent across models, repositories, services, schemas, and tests.
"""

# ── Role names ────────────────────────────────────────────────────────────────
# Must match the role names seeded by the user service (these values
# are extracted directly from the JWT — no DB lookup is performed).

ROLE_ADMIN = "ADMIN"
ROLE_MODERATOR = "MOD"
ROLE_USER = "MEMBER"

# ── Entity status names ───────────────────────────────────────────────────────
# Seeded into the ``entity_status`` table on startup.
# Both threads and comments share this same table.

STATUS_ACTIVE = "ACTIVE"
STATUS_USER_DELETED = "USER_DELETED"
STATUS_MOD_REMOVED = "MOD_REMOVED"

# ── Pagination ────────────────────────────────────────────────────────────────

DEFAULT_CURSOR_LIMIT = 10
MAX_CURSOR_LIMIT = 100

# ── Token ─────────────────────────────────────────────────────────────────────

TOKEN_TYPE_ACCESS = "access"

# ── Error messages ────────────────────────────────────────────────────────────

ERR_INVALID_ACCESS_TOKEN = "Invalid or expired access token"
ERR_THREAD_NOT_FOUND = "Thread not found"
ERR_COMMENT_NOT_FOUND = "Comment not found"
ERR_NOT_AUTHORIZED = "You are not authorized to perform this action"
ERR_ALREADY_LIKED = "You have already liked this"
ERR_NOT_LIKED = "You have not liked this"
ERR_USER_SNAP_NOT_FOUND = "User snapshot not found"
