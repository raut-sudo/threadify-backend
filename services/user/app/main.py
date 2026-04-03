import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.database import Base, async_session, engine
from app.core.logging import configure_logging
from app.repositories.user_repo import seed_default_roles

configure_logging()

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application startup and shutdown lifecycle.

    Startup:
        - Creates all database tables (if they don't exist).
        - Seeds default roles (ADMIN, MOD, MEMBER).
    Shutdown:
        - Disposes the database connection pool.
    """
    logger.info("Starting %s …", settings.APP_NAME)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created / verified")

    async with async_session() as db:
        await seed_default_roles(db)
        await db.commit()
        logger.info("Default roles seeded")

    yield

    await engine.dispose()
    logger.info("%s shut down", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness probe — returns OK if the process is running."""
    return {"status": "ok"}
