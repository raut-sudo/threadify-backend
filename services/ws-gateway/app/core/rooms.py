"""Socket.IO event handlers — connect, disconnect, join_thread, leave_thread.

All four handlers are registered on the ``sio`` singleton from
``socket_manager``.  They are imported (for their side-effects) in
``main.py`` *after* the ``sio`` object is created, so the decorators
fire at the right time.

Authentication flow
-------------------
The client must pass ``{ auth: { token: "<JWT>" } }`` when connecting.
``connect`` verifies the token and stores ``user_id`` + ``username``
in the Socket.IO session so every subsequent handler can retrieve them
without touching Redis or the DB.
"""

import logging

from app.core.auth import verify_token
from app.core.socket_manager import (
    join_thread_room,
    leave_thread_room,
    refresh_ttl,
    register_user,
    sio,
    unregister_user,
)

logger = logging.getLogger(__name__)


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> bool:
    """Authenticate the connecting client.

    Returns ``False`` to refuse the connection if the JWT is missing or invalid.
    On success, stores ``user_id`` and ``username`` in the session and joins
    the ``user:{id}`` room so targeted notifications can be delivered.
    """
    token = (auth or {}).get("token", "")
    claims = verify_token(token)

    if claims is None:
        logger.warning("Connection refused for sid=%s — invalid token", sid)
        return False

    user_id: str = claims["user_id"]
    username: str = claims.get("username", "")

    await sio.save_session(sid, {"user_id": user_id, "username": username})
    await register_user(user_id, sid)

    # Every user is automatically in their own room so notifications are targeted
    await sio.enter_room(sid, f"user:{user_id}")

    logger.info("Connected: sid=%s user=%s username=%s", sid, user_id, username)
    return True


@sio.event
async def disconnect(sid: str) -> None:
    """Clean up Redis state and leave all rooms on disconnect."""
    session = await sio.get_session(sid)
    user_id: str | None = (session or {}).get("user_id")

    if user_id:
        await unregister_user(user_id)
        logger.info("Disconnected: sid=%s user=%s", sid, user_id)
    else:
        logger.warning("Disconnected unknown sid=%s (no session)", sid)


@sio.event
async def join_thread(sid: str, data: dict) -> None:
    """Client opens a thread page — join the ``thread:{id}`` viewer room.

    Expected payload: ``{ "thread_id": "<uuid>" }``
    """
    thread_id = (data or {}).get("thread_id", "")
    if not thread_id:
        logger.warning("join_thread from sid=%s missing thread_id", sid)
        return

    session = await sio.get_session(sid)
    user_id: str | None = (session or {}).get("user_id")
    if not user_id:
        return

    await join_thread_room(user_id, thread_id, sid)
    await refresh_ttl(user_id)


@sio.event
async def leave_thread(sid: str, data: dict) -> None:
    """Client navigates away from a thread — leave the viewer room.

    Expected payload: ``{ "thread_id": "<uuid>" }``
    """
    thread_id = (data or {}).get("thread_id", "")
    if not thread_id:
        return

    session = await sio.get_session(sid)
    user_id: str | None = (session or {}).get("user_id")
    if not user_id:
        return

    await leave_thread_room(user_id, thread_id, sid)
    await refresh_ttl(user_id)
