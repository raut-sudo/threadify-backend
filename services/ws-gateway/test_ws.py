"""
WS Gateway end-to-end test.
Run from services/ws-gateway/ with the venv active:
    .venv/bin/python test_ws.py
"""

import asyncio
import json
import urllib.request

import socketio


def get_token() -> str:
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/auth/login",
        data=json.dumps({"username": "wstest", "password": "Test1234!"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]


async def main():
    print("Getting JWT from user service...")
    token = get_token()
    print(f"  Token: {token[:40]}...\n")

    # ── Test 1: /health ────────────────────────────────────────────────────
    with urllib.request.urlopen("http://localhost:8003/health") as r:
        body = json.loads(r.read())
    assert body == {"status": "ok", "service": "ws-gateway"}, f"Unexpected: {body}"
    print("✅ GET /health →", body)

    # ── Test 2: Valid JWT — connect, join room, leave room, disconnect ─────
    results: dict = {}
    sio = socketio.AsyncClient(logger=False, engineio_logger=False)

    @sio.event
    async def connect():
        results["connected"] = True

    @sio.event
    async def connect_error(data):
        results["error"] = data

    @sio.event
    async def disconnect():
        results["disconnected"] = True

    await sio.connect(
        "http://localhost:8003",
        socketio_path="/ws",
        auth={"token": token},
        wait_timeout=5,
    )
    assert results.get("connected"), f"connect failed, error={results.get('error')}"
    print("✅ Socket.IO connect with valid JWT — OK")

    await sio.emit("join_thread", {"thread_id": "aaaaaaaa-0000-0000-0000-000000000001"})
    await asyncio.sleep(0.3)
    print("✅ join_thread emitted")

    await sio.emit(
        "leave_thread", {"thread_id": "aaaaaaaa-0000-0000-0000-000000000001"}
    )
    await asyncio.sleep(0.3)
    print("✅ leave_thread emitted")

    await sio.disconnect()
    await asyncio.sleep(0.3)
    assert results.get("disconnected"), "disconnect event not fired"
    print("✅ clean disconnect")

    # ── Test 3: Bad token is refused ───────────────────────────────────────
    sio2 = socketio.AsyncClient(logger=False, engineio_logger=False)
    refused = False
    try:
        await sio2.connect(
            "http://localhost:8003",
            socketio_path="/ws",
            auth={"token": "this.is.fake"},
            wait_timeout=3,
        )
    except Exception:
        refused = True
    finally:
        if sio2.connected:
            await sio2.disconnect()
    assert refused, "Bad token should have been refused"
    print("✅ bad token refused — OK")

    # ── Test 4: Missing token is refused ──────────────────────────────────
    sio3 = socketio.AsyncClient(logger=False, engineio_logger=False)
    refused3 = False
    try:
        await sio3.connect(
            "http://localhost:8003",
            socketio_path="/ws",
            auth={},
            wait_timeout=3,
        )
    except Exception:
        refused3 = True
    finally:
        if sio3.connected:
            await sio3.disconnect()
    assert refused3, "Missing token should have been refused"
    print("✅ missing token refused — OK")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
