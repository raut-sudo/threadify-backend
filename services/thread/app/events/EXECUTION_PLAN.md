# Event Bus — Execution Plan

> **Goal:** Emit a RabbitMQ event when a user comments on someone else's thread.
> **Principle:** KISS — minimal files, minimal code, fire-and-forget.

---

## Scope — What We're Building

One event: **`comment.created`**

When `POST /comments` succeeds → publish a message to RabbitMQ with:

```json
{
  "event_type": "COMMENT_CREATED",
  "actor_id": "<commenter uuid>",
  "actor_username": "<commenter username>",
  "target_user_ids": ["<thread owner uuid>"],
  "entity": { "type": "THREAD", "id": "<thread uuid>" },
  "metadata": { "comment_id": "<comment uuid>" }
}
```

Self-comment suppression: if `commenter == thread owner` → don't publish.

---

## Files to Create (3 new files inside `app/events/`)

### 1. `app/events/__init__.py`

Empty package marker. Nothing else.

### 2. `app/events/payloads.py`

Two things only:

1. **`CommentCreatedEvent`** — Pydantic `BaseModel` with all fields typed:
   `event_type`, `actor_id`, `actor_username`, `target_user_ids`, `entity`, `metadata`
2. **`build_comment_created()`** — a plain function that takes the raw UUIDs
   and username and returns a ready-to-publish `CommentCreatedEvent`.
   Self-comment suppression lives here: returns `None` if `actor_id == post_owner_id`.

Using Pydantic gives the notification service a shared contract to validate
against when deserialising, and keeps the service-layer call site clean.

### 3. `app/events/publisher.py`

Single module with three things:

1. **Module-level globals:** `_connection`, `_channel`, `_exchange` (all start `None`)
2. **`connect(url)`** — opens `aio_pika.connect_robust`, declares a durable topic exchange `notification_exchange`
3. **`close()`** — closes connection
4. **`publish(routing_key, payload)`** — calls `payload.model_dump_json()`, publishes
   with `DeliveryMode.PERSISTENT`, wrapped in try/except (log & swallow errors)

The reference code in INSTRUCTIONS.md is almost copy-paste ready.

---

## Files to Modify (4 existing files)

### 3. `app/core/config.py`

Add one setting:

```python
RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
```

### 4. `app/main.py` — lifespan

- Import `app.events.publisher`
- After DB seed, call `publisher.connect(settings.RABBITMQ_URL)` inside try/except (log warning on failure)
- After yield, call `publisher.close()` before engine dispose

### 6. `app/services/comment_service.py` — `create_comment()`

After the comment is persisted and counters updated:

```python
from app.events import publisher
from app.events.payloads import build_comment_created

event = build_comment_created(
    actor_id=user_id,
    actor_username=None,          # UserSnap lookup skipped — best-effort
    post_owner_id=thread.author_id,
    post_id=thread_id,
    comment_id=comment.id,
)
if event:  # None means self-comment — suppressed inside build_comment_created
    await publisher.publish("notification.comment.created", event)
```

`thread` is already loaded at the top of the function — no extra DB query.
`actor_username` is left `None` for now; the notification service can resolve it
from the `user_snap` table using `actor_id` when it consumes the event.
The publish is fire-and-forget; failure is logged, never raised.

**No changes to the route layer** — the event lives in the service layer
where the business logic is.

### 7. `docker-compose.yml`

Add a `rabbitmq` service and wire it to `threadify-net`:

```yaml
rabbitmq:
  image: rabbitmq:3.13-management-alpine
  container_name: rabbitmq
  ports:
    - "5672:5672"
    - "15672:15672"
  networks:
    - threadify-net
  healthcheck:
    test: ["CMD", "rabbitmq-diagnostics", "ping"]
    interval: 10s
    timeout: 10s
    retries: 10
```

Add `RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/` to the
`thread-service` environment block and add `rabbitmq` to its `depends_on`.

### 8. `pyproject.toml`

Add `"aio-pika>=9.0.0"` to dependencies.

---

## Execution Order

| Step | File | What |
|------|------|------|
| 1 | `pyproject.toml` | Add `aio-pika` dependency |
| 2 | `app/core/config.py` | Add `RABBITMQ_URL` setting |
| 3 | `app/events/__init__.py` | Create empty package |
| 4 | `app/events/payloads.py` | `CommentCreatedEvent` schema + `build_comment_created()` builder |
| 5 | `app/events/publisher.py` | Create publisher module (connect/close/publish) |
| 6 | `app/main.py` | Wire connect/close into lifespan |
| 7 | `app/services/comment_service.py` | Publish event after comment creation |
| 8 | `docker-compose.yml` | Add rabbitmq service + thread-service env var |

---

## What We're NOT Doing

- No dead-letter queue setup — that's the consumer's concern (notification service)
- No FastAPI dependency injection for the exchange — the module-level singleton is simpler
- No changes to the route layer — publish lives in the service layer
- No `actor_username` DB lookup at publish time — notification service resolves it from `user_snap`

---

## Dev: Running Without RabbitMQ

The service starts normally even without RabbitMQ:
- `connect()` is wrapped in try/except → logs warning, sets exchange to `None`
- `publish()` checks `if _exchange is None` → logs warning, returns immediately
- Zero impact on `POST /comments` response

To start RabbitMQ locally:

```bash
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.13-management-alpine
```

Management UI: http://localhost:15672 (guest / guest)
