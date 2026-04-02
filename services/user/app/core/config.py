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
    APP_NAME: str = "user-service"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

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
