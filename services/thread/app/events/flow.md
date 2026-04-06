# Event Bus — Flow

End-to-end walkthrough of exactly what happens from the moment a client
POSTs a comment to the moment the notification service would receive the event.

---

## Architecture Overview

```
Client
  │
  │  POST /api/v1/comments
  │  Authorization: Bearer <JWT>
  ▼
Nginx Gateway :8080
  │
  │  proxy_pass → thread-service:8001
  ▼
Thread Service (FastAPI)
  │
  ├─► [1] Authenticate JWT (no DB lookup)
  ├─► [2] Persist comment to PostgreSQL
  ├─► [3] Update counters
  ├─► [4] Build event payload
  ├─► [5] Self-comment check
  └─► [6] Publish to RabbitMQ  ──►  notification_exchange
                                           │
                                           │  routing_key: notification.comment.created
                                           ▼
                                   (future) Notification Service
                                           │
                                           ▼
                                   Push / email / in-app alert to thread owner
```

---

## Step-by-Step Flow

### [1] Request arrives at the route

`POST /api/v1/comments` in [app/api/v1/comments.py](../api/v1/comments.py)

- `get_current_user` dependency extracts the Bearer token
- `jwt.decode(token, PUBLIC_KEY, RS256)` verifies the signature
- Returns `{ "user_id": UUID, "role": str }` — **zero DB queries for auth**

---

### [2] Comment is persisted

`comment_service.create_comment()` in [app/services/comment_service.py](../services/comment_service.py)

```
comment_service.create_comment(db, user_id, thread_id, content, parent_comment_id)
  │
  ├─ thread_repo.get_thread_by_id()          → loads thread + thread.author_id
  ├─ (if reply) comment_repo.get_comment_by_id()  → validates parent exists
  ├─ comment_repo.create_comment()           → INSERT into comments
  ├─ thread_repo.increment_comment_count()   → UPDATE threads SET comment_count + 1
  └─ (if reply) comment_repo.increment_reply_count()
```

The `thread` object loaded in step one already carries `thread.author_id`
(the person who will be notified). No second DB query is needed.

---

### [3] Event payload is built

`build_comment_created()` in [app/events/payloads.py](payloads.py)

```python
event = build_comment_created(
    actor_id      = user_id,          # the commenter (from JWT)
    actor_username= None,             # resolved later by notification-svc via user_snap
    post_owner_id = thread.author_id, # the person to notify (from loaded thread)
    post_id       = thread_id,
    comment_id    = comment.id,
)
```

Returns a `CommentCreatedEvent` Pydantic model:

```json
{
  "event_type":      "COMMENT_CREATED",
  "actor_id":        "11223344-...",
  "actor_username":  null,
  "target_user_ids": ["f1e2d3c4-..."],
  "entity":          { "type": "THREAD", "id": "a1b2c3d4-..." },
  "metadata":        { "comment_id": "b1e2c3d4-..." }
}
```

---

### [4] Self-comment suppression

Inside `build_comment_created()`:

```
actor_id == post_owner_id ?
    │
    ├── YES → return None
    │         publisher.publish() is never called
    │         thread owner commenting on their own thread → no notification
    │
    └── NO  → return CommentCreatedEvent
              proceed to publish
```

---

### [5] Event is published

`publisher.publish()` in [app/events/publisher.py](publisher.py)

```
_exchange.publish(
    Message(
        body             = event.model_dump_json().encode(),
        content_type     = "application/json",
        delivery_mode    = PERSISTENT,     ← survives broker restart
    ),
    routing_key = "notification.comment.created"
)
```

The exchange `notification_exchange` is a **durable topic exchange**.
It was declared at service startup inside `publisher.connect()`.

---

### [6] HTTP response is returned

Regardless of whether the publish succeeded or failed, the route always
returns `201 Created` with the full `CommentResponse` body.

```
publish() outcome       HTTP response
─────────────────────── ─────────────
Published successfully  201 Created ✅
Broker down / error     201 Created ✅  (exception logged, swallowed)
_exchange is None       201 Created ✅  (warning logged, skipped)
Self-comment (None)     201 Created ✅  (no publish attempt)
```

---

## Startup & Shutdown

### Startup (inside `lifespan` in `app/main.py`)

```
1. Create DB tables
2. Seed entity_status rows
3. publisher.connect(RABBITMQ_URL)
      └─ aio_pika.connect_robust(url)          ← auto-reconnects on drops
      └─ channel.declare_exchange(
             "notification_exchange",
             TOPIC, durable=True
         )
   ↑ wrapped in try/except — broker absence only logs a warning,
     service starts normally
```

### Shutdown

```
publisher.close()   → connection.close()
engine.dispose()    → DB pool closed
```

---

## RabbitMQ Topology

```
notification_exchange
    type:    topic
    durable: true

No queues are declared by the thread service.
The notification service declares and binds its own queue:

    queue: threadify.notifications
    binding: notification_exchange  →  routing_key: notification.*
```

The thread service is a **pure producer** — it only publishes.
Queue topology is the consumer's responsibility.

---

## Event Contract (`CommentCreatedEvent`)

Defined in [app/events/payloads.py](payloads.py).

| Field | Type | Description |
|---|---|---|
| `event_type` | `str` | Always `"COMMENT_CREATED"` |
| `actor_id` | `str` (UUID) | User who posted the comment |
| `actor_username` | `str \| null` | Display name — `null` for now, resolved by consumer |
| `target_user_ids` | `list[str]` | UUIDs of users to notify (thread owner) |
| `entity.type` | `str` | Always `"THREAD"` |
| `entity.id` | `str` (UUID) | Thread the comment was posted on |
| `metadata.comment_id` | `str` (UUID) | The new comment's UUID |

---

## For the Notification Service (Consumer)

When you implement `notification-service`, bind a queue to the exchange:

```python
queue = await channel.declare_queue(
    "threadify.notifications",
    durable=True,
    arguments={
        "x-dead-letter-exchange": "threadify.dlx",          # optional DLQ
        "x-dead-letter-routing-key": "threadify.notifications",
    },
)
await queue.bind(exchange, routing_key="notification.*")
```

Consume with `requeue=False` to avoid infinite retry loops on poison messages:

```python
async with queue.iterator() as messages:
    async for message in messages:
        async with message.process(requeue=False):
            event = CommentCreatedEvent.model_validate_json(message.body)
            await handle_comment_created(event)
```

To resolve `actor_username`, query the thread service's `user_snap` table
(or its own user_snap equivalent) using `event.actor_id`.
