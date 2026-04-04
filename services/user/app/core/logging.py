"""Logging configuration for the user service.

Call `configure_logging()` once at application startup — before any
other module-level code runs — to set the root log level, output
format, and silence noisy third-party loggers.

Log-level hierarchy used across the codebase:
    DEBUG   – per-request internals (SQL, token ops, password checks)
    INFO    – business events (user registered, logged in, deleted)
    WARNING – recoverable issues (invalid token, failed auth attempt)
    ERROR   – unexpected failures (DB rollback, unhandled exceptions)
"""

import logging

from app.core.config import get_settings

# Third-party loggers that are excessively verbose at INFO/DEBUG.
# Each is clamped to WARNING so only genuine problems surface.
_NOISY_LOGGERS = [
    "uvicorn.access",
    "uvicorn.error",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "asyncpg",
    "httpcore",
    "httpx",
]


def configure_logging() -> None:
    """Set up structured logging for the entire application.

    Reads ``LOG_LEVEL`` from settings (.env) and applies it to the
    root logger.  All app code uses ``logging.getLogger(__name__)``
    so it inherits this configuration automatically.
    """
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
