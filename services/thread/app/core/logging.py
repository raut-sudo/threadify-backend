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

# Third-party loggers silenced to reduce noise.
#
# uvicorn.access  → WARNING  : suppresses per-request access lines
# uvicorn.error   → CRITICAL : suppresses uvicorn's raw multi-line ERROR
#                               tracebacks — our lifespan handlers log a
#                               clean CRITICAL message before re-raising so
#                               nothing useful is lost.
# watchfiles      → WARNING  : suppresses file-change detection chatter
#                               from --reload mode
# sqlalchemy.*    → WARNING  : suppresses SQL query echo
# asyncpg         → WARNING  : suppresses low-level protocol messages
_NOISY_LOGGERS: dict[str, int] = {
    "uvicorn.access": logging.WARNING,
    "uvicorn.error": logging.CRITICAL,
    "watchfiles": logging.WARNING,
    "watchfiles.main": logging.WARNING,
    "sqlalchemy.engine": logging.WARNING,
    "sqlalchemy.pool": logging.WARNING,
    "asyncpg": logging.WARNING,
    "httpcore": logging.WARNING,
    "httpx": logging.WARNING,
}


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

    for name, level in _NOISY_LOGGERS.items():
        logging.getLogger(name).setLevel(level)
