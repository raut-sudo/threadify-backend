# Notification Service — Execution Plan

> **Scope:** Consume events from RabbitMQ, persist notifications, serve via REST API.
> **Phase 1:** `COMMENT_CREATED` only. `@mentions` deferred to a later phase.
> **Principle:** KISS — minimal files, clean code, same patterns as user & thread services.

---

## Architecture

```
RabbitMQ
  │
  │  notification_exchange (topic, durable)
  │  routing_key: notification.comment.created
  │
  ▼
Notification Service :8002
  ├── Consumer (background task in lifespan)
  │     └── INSERT into notifications table
  │
  ├── REST API
  │     ├── GET  /api/v1/notifications           — paginated list (cursor)
  │     ├── PATCH /api/v1/notifications/{id}/read — mark one read
  │     ├── PATCH /api/v1/notifications/read-all  — mark all read
  │     └── GET  /api/v1/notifications/unread-count
  │
  └── PostgreSQL (notification-db :5435)
```

---

## Event Payload (Produced by Thread Service)

The thread service resolves `actor_username` before publishing (Option B).

```json
{
  "event_type":      "COMMENT_CREATED",
  "actor_id":        "11223344-...",
  "actor_username":  "john_doe",
  "target_user_ids": ["f1e2d3c4-..."],
  "entity":          { "type": "THREAD", "id": "a1b2c3d4-..." },
  "metadata":        { "comment_id": "b1e2c3d4-..." }
}
```

Future event types (e.g. `MENTION_CREATED`) will follow the same shape.

---

## Database — Single Table

```
notifications
────────────────────────────────────────
id              UUID PK (default uuid4)
user_id         UUID NOT NULL INDEX      — the recipient
type            VARCHAR(30) NOT NULL     — "COMMENT_CREATED", "MENTION_CREATED"
actor_id        UUID NOT NULL            — who triggered it
actor_username  VARCHAR(50)              — display name (from event payload)
entity_type     VARCHAR(20) NOT NULL     — "THREAD" or "COMMENT"
entity_id       UUID NOT NULL            — thread_id or comment_id
metadata        JSONB                    — flexible bag (comment_id, etc.)
is_read         BOOLEAN DEFAULT false
created_at      TIMESTAMPTZ DEFAULT now()
```

Index: `(user_id, created_at DESC)` — covers the main query.

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/notifications` | Bearer | Paginated (cursor), filter `?is_read=true/false` |
| PATCH | `/api/v1/notifications/{id}/read` | Bearer (owner) | Mark single notification read |
| PATCH | `/api/v1/notifications/read-all` | Bearer | Mark all unread → read for user |
| GET | `/api/v1/notifications/unread-count` | Bearer | `{ "count": 5 }` |
| GET | `/health` | ✗ | Liveness probe |

---

## Folder Structure

```
services/notification/
    pyproject.toml
    Dockerfile
    .env
    app/
        __init__.py
        main.py
        api/
            __init__.py
            deps.py                    — get_current_user (JWT verify, public key)
            v1/
                __init__.py
                notifications.py       — 4 endpoints
        consumer/
            __init__.py
            worker.py                  — RabbitMQ consumer (background task)
        core/
            __init__.py
            config.py                  — Settings (DB, RabbitMQ, RSA public key)
            database.py                — async engine + session
            exceptions.py
            logging.py
        models/
            __init__.py
            notification.py            — single ORM model
        repositories/
            __init__.py
            notification_repo.py       — CRUD queries
        schemas/
            __init__.py
            notification.py            — Pydantic request/response models
        services/
            __init__.py
            notification_service.py    — business logic
        utils/
            __init__.py
            constants.py
            token.py                   — decode_access_token (public key only)
```

---

## Consumer Design (Option A — Background Task)

Inside `main.py` lifespan:

```
Startup:
  1. Create DB tables
  2. Connect to RabbitMQ (aio_pika.connect_robust)
  3. Declare queue "threadify.notifications" (durable)
  4. Bind to notification_exchange with routing_key "notification.*"
  5. asyncio.create_task(consume_loop(channel, db_session_factory))

Shutdown:
  1. Cancel consumer task
  2. Close RabbitMQ connection
  3. Dispose DB engine
```

`worker.py` consume loop:

```
async for message in queue.iterator():
    async with message.process(requeue=False):
        payload = json.loads(message.body)
        for user_id in payload["target_user_ids"]:
            notification_repo.create_notification(
                user_id      = user_id,
                type         = payload["event_type"],
                actor_id     = payload["actor_id"],
                actor_username = payload["actor_username"],
                entity_type  = payload["entity"]["type"],
                entity_id    = payload["entity"]["id"],
                metadata     = payload["metadata"],
            )
```

On exception → message nacked with `requeue=False` → goes to DLQ (if configured).

---

## Pre-Requisite: Thread Service Change

Before starting the notification service, update the thread service so
`actor_username` is populated in the event payload:

In `comment_service.py`, before calling `build_comment_created()`:

```python
snap = await user_snap_repo.get_user_snap(db, user_id)
actor_username = snap.username if snap else None
```

Then pass `actor_username=actor_username` to the builder.
This is a one-line change + one import.

---

## Execution Order

| Step | File/Folder | What |
|------|-------------|------|
| 0 | thread-service `comment_service.py` | Resolve `actor_username` from `user_snap` before publish |
| 1 | `services/notification/pyproject.toml` | Project setup — fastapi, sqlalchemy, asyncpg, aio-pika, pydantic-settings, python-jose |
| 2 | `app/core/config.py` | Settings: DATABASE_URL, RABBITMQ_URL, RSA_PUBLIC_KEY |
| 3 | `app/core/database.py` | Async engine + session (copy pattern from thread service) |
| 4 | `app/core/logging.py` | configure_logging() (copy pattern) |
| 5 | `app/core/exceptions.py` | AppException base + NotificationNotFoundError |
| 6 | `app/utils/constants.py` | Notification types, error messages |
| 7 | `app/utils/token.py` | decode_access_token (public key verify only — copy from thread service) |
| 8 | `app/api/deps.py` | get_current_user dependency (copy from thread service) |
| 9 | `app/models/notification.py` | Notification ORM model |
| 10 | `app/repositories/notification_repo.py` | create, list, mark_read, mark_all_read, unread_count |
| 11 | `app/schemas/notification.py` | NotificationResponse, NotificationListResponse, UnreadCountResponse |
| 12 | `app/services/notification_service.py` | Thin orchestration layer |
| 13 | `app/consumer/worker.py` | RabbitMQ consume loop |
| 14 | `app/api/v1/notifications.py` | 4 REST endpoints |
| 15 | `app/api/v1/__init__.py` | v1 router |
| 16 | `app/main.py` | Lifespan (DB + consumer + RabbitMQ), exception handlers, health |
| 17 | `Dockerfile` | Python 3.13, uv install, expose 8002 |
| 18 | `docker-compose.yml` | Add notification-db, notification-service, gateway routes |
| 19 | `gateway/nginx.conf` + `nginx.dev.conf` | Add /api/v1/notifications upstream |

---

## What We're NOT Doing (This Phase)

- WebSocket / realtime push
- @mention parsing (thread service will add this later)
- Email / push notification delivery
- Notification preferences / settings
- Batch grouping ("3 people commented on your thread")
- DLQ setup (consumer uses requeue=False — message drops on failure for now)
