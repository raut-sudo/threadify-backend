import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# Pydantic settings for the user service, with caching to avoid reloading on every access
class Settings(BaseSettings):
    DATABASE_URL: str
    RSA_PRIVATE_KEY: str
    RSA_PUBLIC_KEY: str
    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # ── RabbitMQ ──────────────────────────────────
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    APP_NAME: str = "user-service"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Bootstrap admin credentials — used only at first startup to seed the admin user.
    # After the user row exists, these are never read again.
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@threadify.com"
    ADMIN_PASSWORD: str = "Admin@123!"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    logger.info(
        "Settings loaded: APP_NAME=%s, DEBUG=%s, LOG_LEVEL= %s",
        settings.APP_NAME,
        settings.DEBUG,
        settings.LOG_LEVEL,
    )
    return settings
