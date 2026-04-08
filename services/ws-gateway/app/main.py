"""WebSocket Gateway — FastAPI + Socket.IO application entry point.

Architecture
------------
Socket.IO runs as an ASGI sub-application mounted at ``/ws``.
FastAPI handles the ``/health`` liveness probe and nothing else —
all real-time work happens through Socket.IO events.

Startup sequence (inside ``lifespan``):
  1. init_redis()                     — open Redis connection pool
  2. asyncio.create_task(start_consumer()) — RabbitMQ consumer background loop

Shutdown:
  - Consumer task cancelled automatically when the event loop stops.
  - close_redis()                     — drain Redis connection pool.

Socket.IO event handlers are registered by importing ``app.core.rooms``
as a side-effect before the ``sio`` object is handed to ``socketio.ASGIApp``.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.consumers.rabbitmq import start_consumer
from app.core import rooms as _rooms_module  # noqa: F401 — registers sio event handlers
from app.core.logging import configure_logging
from app.core.socket_manager import close_redis, init_redis, sio

configure_logging()

logger = logging.getLogger(__name__)
settings = get_settings()

_consumer_task: asyncio.Task | None = None


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _consumer_task

    logger.info("Starting %s …", settings.APP_NAME)

    # 1. Redis
    try:
        await init_redis()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis unavailable (%s) — connection state disabled", exc)

    # 2. RabbitMQ consumer
    try:
        _consumer_task = asyncio.create_task(start_consumer())
        logger.info("Realtime consumer task started")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "RabbitMQ consumer failed to start (%s) — realtime disabled", exc
        )

    yield

    # Shutdown
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")

    await close_redis()
    logger.info("%s shut down", settings.APP_NAME)


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Liveness probe — returns OK if the process is running."""
    return JSONResponse({"status": "ok", "service": settings.APP_NAME})


# ── Socket.IO ASGI mount ──────────────────────────────────────────────────────
# The Socket.IO ASGI app intercepts all requests to /ws (both HTTP long-poll
# and WebSocket upgrade).  FastAPI only sees paths that don't start with /ws.

socket_app = socketio.ASGIApp(sio, socketio_path="")
app.mount("/ws", socket_app)
