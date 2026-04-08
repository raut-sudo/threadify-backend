"""Thread service — FastAPI application entry point.

Startup sequence (inside ``lifespan``):
  1. Create all ORM tables via ``Base.metadata.create_all``.
  2. Seed the ``entity_status`` lookup table (ACTIVE / USER_DELETED / MOD_REMOVED).

Shutdown:
  - Dispose the async engine connection pool cleanly.

Exception handlers:
  - ``RequestValidationError`` → 422 with Pydantic field-level errors.
  - ``AppException``           → domain status code + detail JSON.
  - ``Exception``              → 500 Internal Server Error (safe message).
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.consumer.worker import consume as consume_user_snaps
from app.core.config import get_settings
from app.core.database import Base, async_session, engine
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.events import publisher
from app.repositories.seed import seed_entity_statuses

configure_logging()

logger = logging.getLogger(__name__)
settings = get_settings()

_consumer_task: asyncio.Task | None = None


def _masked_db_url() -> str:
    """Return the DATABASE_URL with the password replaced by ***."""
    url = settings.DATABASE_URL
    if "@" in url and ":" in url.split("@")[0]:
        creds, rest = url.split("@", 1)
        scheme_user, _ = creds.rsplit(":", 1)
        return f"{scheme_user}:***@{rest}"
    return url


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application startup and shutdown lifecycle.

    Startup:
        - Creates all database tables (if they don't exist).
        - Seeds entity statuses: ACTIVE, USER_DELETED, MOD_REMOVED.
    Shutdown:
        - Disposes the database connection pool.
    """
    logger.info("Starting %s …", settings.APP_NAME)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created / verified")

    async with async_session() as db:
        await seed_entity_statuses(db)
        await db.commit()
        logger.info("Entity statuses seeded")

    # Connect the RabbitMQ publisher (notification + realtime exchanges)
    await publisher.connect(settings.RABBITMQ_URL)

    # Start UserSnap consumer — keeps the local author cache in sync with user-service
    global _consumer_task
    try:
        _consumer_task = asyncio.create_task(
            consume_user_snaps(settings.RABBITMQ_URL, async_session)
        )
        logger.info("UserSnap consumer task started")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "UserSnap consumer failed to start (%s) — author info may be stale", exc
        )

    yield

    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        logger.info("UserSnap consumer task cancelled")

    await publisher.close()
    await engine.dispose()
    logger.info("%s shut down", settings.APP_NAME)


# ── Application ───────────────────────────────────────────────────────────────


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)


# ── Exception handlers ────────────────────────────────────────────────────────


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a structured 422 with every field-level validation error."""
    logger.warning(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Convert any domain AppException into a structured JSON response."""
    logger.warning(
        "Domain error on %s %s: [%s] %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected errors — log full traceback, return safe 500."""
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ── Router ────────────────────────────────────────────────────────────────────


app.include_router(v1_router, prefix="/api/v1")


# ── Health check ──────────────────────────────────────────────────────────────


@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness probe — returns OK if the process is running."""
    return {"status": "ok"}
