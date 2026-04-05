"""Custom application exceptions for the thread service.

Every domain error is a subclass of ``AppException`` which carries an
HTTP status code and a detail message.  The global exception handler
registered in ``main.py`` converts these into JSON responses
automatically, keeping the service layer free of any FastAPI imports.

Usage
-----
Raise with no arguments to use the class-level default message::

    raise ThreadNotFoundError()

Or override the message at the call-site when extra context helps::

    raise ThreadNotFoundError(f"Thread {thread_id} does not exist.")

Error message strings live in ``app/utils/constants.py``.
"""

from app.utils.constants import (
    ERR_ALREADY_LIKED,
    ERR_COMMENT_NOT_FOUND,
    ERR_INVALID_ACCESS_TOKEN,
    ERR_NOT_AUTHORIZED,
    ERR_NOT_LIKED,
    ERR_THREAD_NOT_FOUND,
    ERR_USER_SNAP_NOT_FOUND,
)

# ── Base exception ────────────────────────────────────────────────────────────


class AppException(Exception):
    """Base class for all domain exceptions.

    Subclasses declare ``status_code``, ``detail``, and optionally
    ``headers`` as class attributes.  ``detail`` may be overridden per
    instance by passing a string to ``__init__``.
    """

    status_code: int = 500
    detail: str = "An unexpected error occurred"
    headers: dict | None = None

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


# ── Thread exceptions ─────────────────────────────────────────────────────────


class ThreadNotFoundError(AppException):
    """Raised when a thread lookup by ID returns nothing."""

    status_code = 404
    detail = ERR_THREAD_NOT_FOUND


# ── Comment exceptions ────────────────────────────────────────────────────────


class CommentNotFoundError(AppException):
    """Raised when a comment lookup by ID returns nothing."""

    status_code = 404
    detail = ERR_COMMENT_NOT_FOUND


# ── Authorization exceptions ──────────────────────────────────────────────────


class NotAuthorizedError(AppException):
    """Raised when a user attempts an action they do not have permission for.

    Covers both ownership checks (non-author trying to edit/delete) and
    role checks (non-moderator trying a mod-only action).
    """

    status_code = 403
    detail = ERR_NOT_AUTHORIZED


class InvalidAccessTokenError(AppException):
    """Raised when the Bearer token is missing, malformed, expired, or
    signed with an unrecognised key."""

    status_code = 401
    detail = ERR_INVALID_ACCESS_TOKEN
    headers = {"WWW-Authenticate": "Bearer"}


# ── Like exceptions ───────────────────────────────────────────────────────────


class AlreadyLikedError(AppException):
    """Raised when a user attempts to like something they have already liked."""

    status_code = 409
    detail = ERR_ALREADY_LIKED


class NotLikedError(AppException):
    """Raised when a user attempts to unlike something they have not liked."""

    status_code = 409
    detail = ERR_NOT_LIKED


# ── User snapshot exceptions ──────────────────────────────────────────────────


class UserSnapNotFoundError(AppException):
    """Raised when a user snapshot lookup returns nothing."""

    status_code = 404
    detail = ERR_USER_SNAP_NOT_FOUND
