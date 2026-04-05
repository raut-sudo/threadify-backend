"""Database engine, session factory, ORM base, and session dependency.

Wiring
------
- ``engine``        — module-level async engine; shared across the process.
- ``async_session`` — session factory; each request gets its own session.
- ``Base``          — all ORM models inherit from this.
- ``get_db()``      — FastAPI dependency that yields a session, commits on
                      clean exit, rolls back only on unexpected errors, and
                      always closes the session.

Commit / rollback strategy
--------------------------
``HTTPException``, ``RequestValidationError`` and ``AppException`` are all
expected control-flow signals — they indicate a bad request or a domain
rule violation, *not* a DB consistency problem.  Rolling back for those
would silently discard any writes that were intentional (e.g. an audit
log written before the error was raised).  Generic ``Exception`` is the
only case where we truly don't know the DB state, so that's the only
case we roll back.
"""

import logging
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Engine ───────────────────────────────────────────────────────────────────
# NOTE: Do NOT set echo=True here — it bypasses Python's logging hierarchy and
# duplicates every SQL statement.  Set LOG_LEVEL=DEBUG in .env for SQL output.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Recycles stale connections before use
)
logger.info("Database engine created for: %s", settings.DATABASE_URL.split("@")[-1])

# ── Session factory ──────────────────────────────────────────────────────────
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevents lazy-load errors after commit in async context
)


# ── ORM base ─────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Session dependency ───────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the lifetime of a single request."""
    async with async_session() as session:
        logger.debug("DB session opened")
        try:
            yield session
            await session.commit()
            logger.debug("DB session committed")
        except (HTTPException, RequestValidationError, AppException):
            # Known control-flow exceptions — no rollback needed.
            raise
        except Exception:
            await session.rollback()
            logger.exception("DB session rolled back due to unexpected error")
            raise
        finally:
            logger.debug("DB session closed")
