"""Notification service — FastAPI application entry point.

Startup sequence (inside ``lifespan``):
  1. Create all ORM tables via ``Base.metadata.create_all``.
  2. Start RabbitMQ consumer as a background asyncio task.

Shutdown:
  - Cancel the consumer task.
  - Dispose the async engine connection pool.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.consumer.worker import consume
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.events import publisher as realtime_publisher

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
    """Application startup and shutdown lifecycle."""
    global _consumer_task

    logger.info("Starting %s …", settings.APP_NAME)
    logger.info("Database: %s", _masked_db_url())

    # 1. Create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created / verified")

    # 2. Start RabbitMQ consumer as background task
    try:
        from app.core.database import async_session

        _consumer_task = asyncio.create_task(
            consume(settings.RABBITMQ_URL, async_session)
        )
        logger.info("RabbitMQ consumer started")
    except Exception as exc:  # noqa: BLE001
        logger.warning("RabbitMQ consumer failed to start (%s) — events disabled", exc)

    # 3. Connect realtime publisher
    try:
        await realtime_publisher.connect(settings.RABBITMQ_URL)
        logger.info("Realtime publisher connected")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Realtime publisher failed to connect (%s) — realtime events disabled", exc
        )

    yield

    # Shutdown
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")

    await realtime_publisher.close()
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
