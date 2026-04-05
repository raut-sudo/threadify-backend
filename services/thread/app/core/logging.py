"""Logging configuration for the thread service.

Call ``configure_logging()`` once at application startup — before any
other module-level code runs — to set the root log level, output
format, and silence noisy third-party loggers.

Log-level conventions used across this codebase
------------------------------------------------
DEBUG   – per-request internals (SQL queries, token decoding, session lifecycle)
INFO    – business events (thread created, comment deleted, like toggled)
WARNING – recoverable issues (invalid token presented, unauthorized attempt)
ERROR   – unexpected failures (DB rollback, unhandled exceptions)
"""

import logging

from app.core.config import get_settings

# Third-party loggers that flood output at INFO/DEBUG.
# Clamped to WARNING so only genuine problems surface.
_NOISY_LOGGERS: list[str] = [
    "uvicorn.access",
    "uvicorn.error",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "asyncpg",
    "httpcore",
    "httpx",
]


def configure_logging() -> None:
    """Configure structured logging for the entire application.

    Reads ``LOG_LEVEL`` from settings (populated from ``.env``) and
    applies it to the root logger.  All application code uses
    ``logging.getLogger(__name__)`` so it inherits this configuration
    automatically without any per-module setup.
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
