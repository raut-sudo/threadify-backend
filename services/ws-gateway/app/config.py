"""Application settings for the WebSocket gateway.

Loaded once from the ``.env`` file and cached via ``lru_cache``.
No database — only Redis, RabbitMQ, and JWT verification.
"""

import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ── Redis (connection state) ─────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6381"

    # ── RabbitMQ ─────────────────────────────────────────────────────────────
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # ── JWT (verify-only — same public key as other services) ────────────────
    RSA_PUBLIC_KEY: str = ""
    JWT_ALGORITHM: str = "RS256"

    # ── Socket.IO ────────────────────────────────────────────────────────────
    SOCKET_PATH: str = "/ws"
    PING_INTERVAL: int = 25
    PING_TIMEOUT: int = 10
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "ws-gateway"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    logger.info(
        "Settings loaded: APP_NAME=%s DEBUG=%s LOG_LEVEL=%s",
        settings.APP_NAME,
        settings.DEBUG,
        settings.LOG_LEVEL,
    )
    return settings
