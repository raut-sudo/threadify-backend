"""
Custom application exceptions for the user service.

Every domain error is a subclass of ``AppException`` which carries an
HTTP status code and a detail message.  The global handler registered
in ``app/main.py`` converts them to JSON responses automatically,
keeping the service layer free of FastAPI imports.

Usage
-----
Raise without arguments to use the class-level default message::

    raise UsernameTakenError()

Or override the message at the call-site::

    raise UserNotFoundError("No user with that ID exists.")
"""

from app.utils.constants import (
    ERR_ACCOUNT_ALREADY_DELETED,
    ERR_ACCOUNT_DELETED,
    ERR_DEFAULT_ROLE_MISSING,
    ERR_EMAIL_REGISTERED,
    ERR_INVALID_ACCESS_TOKEN,
    ERR_INVALID_CREDENTIALS,
    ERR_INVALID_REFRESH_TOKEN,
    ERR_USER_NOT_FOUND,
    ERR_USER_UNAVAILABLE,
    ERR_USERNAME_TAKEN,
)


class AppException(Exception):
    """Base class for all domain exceptions.

    Subclasses declare ``status_code``, ``detail``, and optionally
    ``headers`` as class attributes.
    """

    status_code: int = 500
    detail: str = "An unexpected error occurred"
    headers: dict | None = None

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


# ── Auth Exceptions ─────────────────────────────────


class UsernameTakenError(AppException):
    """Raised when the requested username is already in use."""

    status_code = 409
    detail = ERR_USERNAME_TAKEN


class EmailAlreadyRegisteredError(AppException):
    """Raised when the requested email is already registered."""

    status_code = 409
    detail = ERR_EMAIL_REGISTERED


class DefaultRoleMissingError(AppException):
    """Raised when the MEMBER role has not been seeded in the database."""

    status_code = 500
    detail = ERR_DEFAULT_ROLE_MISSING


class InvalidCredentialsError(AppException):
    """Raised when username/password do not match."""

    status_code = 401
    detail = ERR_INVALID_CREDENTIALS


class AccountDeletedError(AppException):
    """Raised when the user's account has been soft-deleted."""

    status_code = 403
    detail = ERR_ACCOUNT_DELETED


class InvalidRefreshTokenError(AppException):
    """Raised when a refresh token is missing, revoked, or expired."""

    status_code = 401
    detail = ERR_INVALID_REFRESH_TOKEN


class UserUnavailableError(AppException):
    """Raised when the user linked to a refresh token no longer exists or is deleted."""

    status_code = 401
    detail = ERR_USER_UNAVAILABLE


class InvalidAccessTokenError(AppException):
    """Raised when the Bearer token is invalid, expired, or the user is gone."""

    status_code = 401
    detail = ERR_INVALID_ACCESS_TOKEN
    headers = {"WWW-Authenticate": "Bearer"}


# ── User Exceptions ─────────────────────────────────


class UserNotFoundError(AppException):
    """Raised when a user lookup by ID returns nothing."""

    status_code = 404
    detail = ERR_USER_NOT_FOUND


class AccountAlreadyDeletedError(AppException):
    """Raised when trying to delete an account that is already deleted."""

    status_code = 409
    detail = ERR_ACCOUNT_ALREADY_DELETED
