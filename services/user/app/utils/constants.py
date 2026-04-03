"""Centralised constants for the user service.

Keeps magic strings and numbers in one place so they stay
consistent across services, repos, schemas, and tests.
"""

# ── Role Names ──────────────────────────────────────

ROLE_ADMIN = "ADMIN"
ROLE_MOD = "MOD"
ROLE_MEMBER = "MEMBER"

DEFAULT_ROLES: list[tuple[str, str]] = [
    (ROLE_ADMIN, "Full platform access"),
    (ROLE_MOD, "Community moderation privileges"),
    (ROLE_MEMBER, "Standard registered user"),
]

# ── Token Types ─────────────────────────────────────

TOKEN_TYPE_BEARER = "bearer"
TOKEN_TYPE_ACCESS = "access"

# ── Pagination ──────────────────────────────────────

DEFAULT_PAGE_SKIP = 0
DEFAULT_PAGE_LIMIT = 50

# ── Validation Constraints ──────────────────────────

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
USERNAME_PATTERN = r"^[a-zA-Z0-9_]+$"

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

# ── Error Messages ──────────────────────────────────

ERR_USERNAME_TAKEN = "Username already taken"
ERR_EMAIL_REGISTERED = "Email already registered"
ERR_INVALID_CREDENTIALS = "Invalid username or password"
ERR_ACCOUNT_DELETED = "Account has been deleted"
ERR_ACCOUNT_ALREADY_DELETED = "Account is already deleted"
ERR_USER_NOT_FOUND = "User not found"
ERR_USER_UNAVAILABLE = "User account unavailable"
ERR_INVALID_REFRESH_TOKEN = "Invalid or expired refresh token"
ERR_DEFAULT_ROLE_MISSING = "Default role not found — database may not be seeded"
