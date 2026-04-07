"""Logging configuration for the WS gateway.

Call ``configure_logging()`` once at application startup (inside lifespan).
"""

import logging

from app.config import get_settings

_NOISY_LOGGERS: dict[str, int] = {
    "uvicorn.access": logging.WARNING,
    "uvicorn.error": logging.CRITICAL,
    "watchfiles": logging.WARNING,
    "watchfiles.main": logging.WARNING,
    "httpcore": logging.WARNING,
    "httpx": logging.WARNING,
    "aio_pika": logging.WARNING,
    "socketio": logging.WARNING,
    "engineio": logging.WARNING,
}


def configure_logging() -> None:
    """Configure structured logging for the entire application."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    for name, lvl in _NOISY_LOGGERS.items():
        logging.getLogger(name).setLevel(lvl)
