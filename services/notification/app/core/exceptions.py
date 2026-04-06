"""Custom application exceptions for the notification service."""

from app.utils.constants import (
    ERR_INVALID_ACCESS_TOKEN,
    ERR_NOT_AUTHORIZED,
    ERR_NOTIFICATION_NOT_FOUND,
)

# ── Base exception ────────────────────────────────────────────────────────────


class AppException(Exception):
    """Base class for all domain exceptions."""

    status_code: int = 500
    detail: str = "An unexpected error occurred"
    headers: dict | None = None

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


# ── Notification exceptions ───────────────────────────────────────────────────


class NotificationNotFoundError(AppException):
    status_code = 404
    detail = ERR_NOTIFICATION_NOT_FOUND


# ── Authorization exceptions ──────────────────────────────────────────────────


class NotAuthorizedError(AppException):
    status_code = 403
    detail = ERR_NOT_AUTHORIZED


class InvalidAccessTokenError(AppException):
    status_code = 401
    detail = ERR_INVALID_ACCESS_TOKEN
    headers = {"WWW-Authenticate": "Bearer"}
