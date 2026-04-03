import logging
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# 1. Async engine
# NOTE: Do NOT set echo=True here — it bypasses Python's logging
# hierarchy and duplicates every SQL statement.  If you need SQL
# output for debugging, set LOG_LEVEL=DEBUG in .env instead.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
logger.info("Database engine created: %s", settings.DATABASE_URL.split("@")[-1])

# 2. Session factory
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevents lazy-load errors after commit in async
)


# 3. ORM base class
class Base(DeclarativeBase):
    pass


# 4. DB session dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        logger.debug("DB session opened")
        try:
            yield session
            await session.commit()
            logger.debug("DB session committed")
        except HTTPException:
            # Business-logic errors (4xx/5xx) are normal control flow.
            # No rollback needed — the session had no pending writes.
            raise
        except Exception:
            await session.rollback()
            logger.exception("DB session rolled back")
            raise
        finally:
            logger.debug("DB session closed")
