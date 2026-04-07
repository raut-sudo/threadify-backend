"""Socket.IO server instance and Redis connection-state helpers.

All Redis keys carry a 30-minute TTL that is refreshed by client heartbeats.
This module is the single source of truth for the ``sio`` object — import it
everywhere you need to emit events.

Key schema
----------
``user:{id}:sid``      STRING   socket ID of the connected user
``user:{id}:online``   STRING   "1" — presence flag
``user:{id}:rooms``    SET      thread-room names the user has joined
``thread:{id}:viewers`` SET     user IDs currently viewing this thread
"""

import logging

import redis.asyncio as aioredis
import socketio

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_TTL = 1800  # 30 minutes

# ── Socket.IO server (module-level singleton) ─────────────────────────────────
sio: socketio.AsyncServer = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_interval=settings.PING_INTERVAL,
    ping_timeout=settings.PING_TIMEOUT,
)

# ── Redis client (initialised in init_redis) ──────────────────────────────────
_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    """Open a Redis connection pool.  Called once in lifespan startup."""
    global _redis
    _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await _redis.ping()
    logger.info("Redis connected: %s", settings.REDIS_URL)


async def close_redis() -> None:
    """Close the Redis connection pool.  Called in lifespan shutdown."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


# ── Key helpers ───────────────────────────────────────────────────────────────


def _sid_key(user_id: str) -> str:
    return f"user:{user_id}:sid"


def _online_key(user_id: str) -> str:
    return f"user:{user_id}:online"


def _rooms_key(user_id: str) -> str:
    return f"user:{user_id}:rooms"


def _viewers_key(thread_id: str) -> str:
    return f"thread:{thread_id}:viewers"


# ── State operations ──────────────────────────────────────────────────────────


async def register_user(user_id: str, sid: str) -> None:
    """Record that *user_id* is connected with socket *sid*."""
    if not _redis:
        return
    pipe = _redis.pipeline()
    pipe.set(_sid_key(user_id), sid, ex=_TTL)
    pipe.set(_online_key(user_id), "1", ex=_TTL)
    await pipe.execute()
    logger.debug("Registered user=%s sid=%s", user_id, sid)


async def unregister_user(user_id: str) -> None:
    """Remove all connection state for *user_id* and clean up viewer sets."""
    if not _redis:
        return

    rooms = await _redis.smembers(_rooms_key(user_id))

    pipe = _redis.pipeline()
    for room in rooms:
        # room is stored as the bare thread_id
        pipe.srem(_viewers_key(room), user_id)
    pipe.delete(_sid_key(user_id))
    pipe.delete(_online_key(user_id))
    pipe.delete(_rooms_key(user_id))
    await pipe.execute()
    logger.debug("Unregistered user=%s (cleaned %d rooms)", user_id, len(rooms))


async def join_thread_room(user_id: str, thread_id: str, sid: str) -> None:
    """Add *user_id* as a viewer of *thread_id* and enter the socketio room."""
    if _redis:
        pipe = _redis.pipeline()
        pipe.sadd(_viewers_key(thread_id), user_id)
        pipe.sadd(_rooms_key(user_id), thread_id)
        pipe.expire(_viewers_key(thread_id), _TTL)
        pipe.expire(_rooms_key(user_id), _TTL)
        await pipe.execute()

    await sio.enter_room(sid, f"thread:{thread_id}")
    logger.debug("user=%s joined thread room=%s", user_id, thread_id)


async def leave_thread_room(user_id: str, thread_id: str, sid: str) -> None:
    """Remove *user_id* from the *thread_id* viewer set and leave the room."""
    if _redis:
        pipe = _redis.pipeline()
        pipe.srem(_viewers_key(thread_id), user_id)
        pipe.srem(_rooms_key(user_id), thread_id)
        await pipe.execute()

    await sio.leave_room(sid, f"thread:{thread_id}")
    logger.debug("user=%s left thread room=%s", user_id, thread_id)


async def refresh_ttl(user_id: str) -> None:
    """Reset the expiry on all user keys (called on heartbeat / any message)."""
    if not _redis:
        return
    pipe = _redis.pipeline()
    pipe.expire(_sid_key(user_id), _TTL)
    pipe.expire(_online_key(user_id), _TTL)
    pipe.expire(_rooms_key(user_id), _TTL)
    await pipe.execute()
