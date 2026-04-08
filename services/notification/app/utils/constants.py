"""Centralised constants for the notification service."""

# ── Notification types ────────────────────────────────────────────────────────

NOTIF_TYPE_COMMENT_CREATED = "COMMENT_CREATED"
NOTIF_TYPE_MENTION_CREATED = "MENTION_CREATED"

# ── Pagination ────────────────────────────────────────────────────────────────

DEFAULT_CURSOR_LIMIT = 20
MAX_CURSOR_LIMIT = 100

# ── Token ─────────────────────────────────────────────────────────────────────

TOKEN_TYPE_ACCESS = "access"

# ── Error messages ────────────────────────────────────────────────────────────

ERR_INVALID_ACCESS_TOKEN = "Invalid or expired access token"
ERR_NOT_AUTHORIZED = "You are not authorized to perform this action"
ERR_NOTIFICATION_NOT_FOUND = "Notification not found"
