"""Application settings for the thread service.

Uses ``pydantic-settings`` to load configuration from the ``.env`` file
and environment variables.  The ``get_settings()`` factory is cached
with ``lru_cache`` so the file is only parsed once per process.

This service only *verifies* JWTs — it never issues them — so only the
RSA public key is required here (no private key).
"""

import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────
    DATABASE_URL: str

    # ── JWT (verify-only — no private key needed) ────
    RSA_PUBLIC_KEY: str
    JWT_ALGORITHM: str = "RS256"

    # ── RabbitMQ ──────────────────────────────────
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # ── Application ──────────────────────────────────
    APP_NAME: str = "thread-service"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    logger.info(
        "Settings loaded: APP_NAME=%s, DEBUG=%s, LOG_LEVEL=%s",
        settings.APP_NAME,
        settings.DEBUG,
        settings.LOG_LEVEL,
    )
    return settings
