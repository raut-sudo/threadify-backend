# Thread & Comment Service — Execution Plan

> **Reference:** [implementation_guide.md](implementation_guide.md)
> **User Service (structure reference):** `services/user/`
> **Decisions:** UUID for all PKs · Shared status table for threads & comments · Unlike endpoints included

---

## Step 1 — Project Setup & Infrastructure

### Files

| Action | Path |
|--------|------|
| UPDATE | `services/thread/pyproject.toml` |
| UPDATE | `docker-compose.yml` |
| CREATE | `services/thread/.env` |

### Details

- **`pyproject.toml`** — Add all required dependencies:
  - `fastapi[standard]`, `asyncpg`, `sqlalchemy`, `pydantic-settings`, `python-jose[cryptography]`, `pydantic`, `cryptography`
  - Dev: `ruff`
- **`docker-compose.yml`** — Add a `thread-db` Postgres service:
  - Image: `postgres:16-alpine`
  - Env: `POSTGRES_USER=thread`, `POSTGRES_PASSWORD=password`, `POSTGRES_DB=thread_db`
  - Port: `5434:5432`
  - Volume: `thread-db-data`
- **`.env`** — Environment variables:
  - `DATABASE_URL` (async pg connection string pointing to thread-db)
  - `RSA_PUBLIC_KEY` (public key for JWT verification — verify only, no private key)
  - `JWT_ALGORITHM=RS256`
  - `APP_NAME=thread-service`
  - `DEBUG=False`
  - `LOG_LEVEL=INFO`

---

## Step 2 — Core Layer (`app/core/`)

### Files

| Action | Path |
|--------|------|
| CREATE | `services/thread/app/core/__init__.py` |
| CREATE | `services/thread/app/core/config.py` |
| CREATE | `services/thread/app/core/database.py` |
| CREATE | `services/thread/app/core/logging.py` |
| CREATE | `services/thread/app/core/exceptions.py` |

### Details

- **`config.py`** — `Settings(BaseSettings)` with fields: `DATABASE_URL`, `RSA_PUBLIC_KEY`, `JWT_ALGORITHM`, `APP_NAME`, `DEBUG`, `LOG_LEVEL`. Cached `get_settings()`. *(Reference: `services/user/app/core/config.py` — no private key needed, this service only verifies tokens.)*
- **`database.py`** — Async engine via `create_async_engine`, `async_sessionmaker`, `Base(DeclarativeBase)`, `get_db()` async generator with commit/rollback. *(Reference: `services/user/app/core/database.py`)*
- **`logging.py`** — `configure_logging()` — reads `LOG_LEVEL` from settings, configures `basicConfig`, silences noisy loggers. *(Reference: `services/user/app/core/logging.py`)*
- **`exceptions.py`** — Base `AppException(status_code, detail)` + domain errors:
  - `ThreadNotFoundError(404)`
  - `CommentNotFoundError(404)`
  - `NotAuthorizedError(403)`
  - `AlreadyLikedError(409)`
  - `NotLikedError(409)`
  - `InvalidAccessTokenError(401)`

---

## Step 3 — Constants & JWT Verification Utility (`app/utils/`)

### Files

| Action | Path |
|--------|------|
| CREATE | `services/thread/app/utils/__init__.py` |
| CREATE | `services/thread/app/utils/constants.py` |
| CREATE | `services/thread/app/utils/token.py` |

### Details

- **`constants.py`** — All string constants:
  - Roles: `ROLE_ADMIN`, `ROLE_MODERATOR`, `ROLE_USER`
  - Statuses: `STATUS_ACTIVE`, `STATUS_USER_DELETED`, `STATUS_MOD_REMOVED`
  - Pagination: `DEFAULT_CURSOR_LIMIT = 10`
  - Error messages: `ERR_THREAD_NOT_FOUND`, `ERR_COMMENT_NOT_FOUND`, `ERR_NOT_AUTHORIZED`, `ERR_ALREADY_LIKED`, `ERR_NOT_LIKED`, `ERR_INVALID_TOKEN`, etc.
- **`token.py`** — `decode_access_token(token: str) -> dict | None`
  - Uses `RSA_PUBLIC_KEY` from settings + `python-jose` to verify RS256 JWT
  - Returns `{"user_id": <uuid>, "role": <str>}` or `None`
  - No token creation — verify only

---

## Step 4 — Database Models (`app/models/`)

### Files

| Action | Path |
|--------|------|
| CREATE | `services/thread/app/models/__init__.py` |
| CREATE | `services/thread/app/models/entity_status.py` |
| CREATE | `services/thread/app/models/thread.py` |
| CREATE | `services/thread/app/models/comment.py` |
| CREATE | `services/thread/app/models/thread_like.py` |
| CREATE | `services/thread/app/models/comment_like.py` |
| CREATE | `services/thread/app/models/user_snap.py` |

### Details

> All primary keys are **UUID**. All foreign keys referencing PKs are also UUID.

- **`entity_status.py`** — **Shared** status table used by both threads and comments:
  ```
  entity_status { id UUID PK, name VARCHAR UNIQUE, description VARCHAR NULL, created_at TIMESTAMP }
  ```
  Seeded values: `ACTIVE`, `USER_DELETED`, `MOD_REMOVED`

- **`thread.py`** — Threads table:
  ```
  threads { id UUID PK, title TEXT, content TEXT, author_id UUID,
            status_id UUID FK→entity_status.id, deleted_at TIMESTAMP NULL,
            like_count INT DEFAULT 0, comment_count INT DEFAULT 0,
            created_at TIMESTAMP, updated_at TIMESTAMP }
  ```
  Relationships: `status` (joined → entity_status), `likes`, `comments`

- **`comment.py`** — Comments table:
  ```
  comments { id UUID PK, thread_id UUID FK→threads.id, parent_comment_id UUID FK→comments.id NULL,
             author_id UUID, content TEXT, status_id UUID FK→entity_status.id,
             deleted_at TIMESTAMP NULL, like_count INT DEFAULT 0,
             reply_count INT DEFAULT 0, created_at TIMESTAMP }
  ```
  Relationships: `status` (joined → entity_status), `parent` (self-referential), `replies`

- **`thread_like.py`** — Thread likes:
  ```
  thread_likes { id UUID PK, user_id UUID, thread_id UUID FK→threads.id,
                 created_at TIMESTAMP, UNIQUE(user_id, thread_id) }
  ```

- **`comment_like.py`** — Comment likes:
  ```
  comment_likes { id UUID PK, user_id UUID, comment_id UUID FK→comments.id,
                  created_at TIMESTAMP, UNIQUE(user_id, comment_id) }
  ```

- **`user_snap.py`** — Denormalized user display data:
  ```
  user_snap { user_id UUID PK, username VARCHAR, avatar_url TEXT NULL, updated_at TIMESTAMP }
  ```

- **`__init__.py`** — Re-exports all models: `EntityStatus`, `Thread`, `Comment`, `ThreadLike`, `CommentLike`, `UserSnap`

---

## Step 5 — Pydantic Schemas (`app/schemas/`)

### Files

| Action | Path |
|--------|------|
| CREATE | `services/thread/app/schemas/__init__.py` |
| CREATE | `services/thread/app/schemas/common.py` |
| CREATE | `services/thread/app/schemas/thread.py` |
| CREATE | `services/thread/app/schemas/comment.py` |
| CREATE | `services/thread/app/schemas/like.py` |
| CREATE | `services/thread/app/schemas/user_snap.py` |

### Details

- **`common.py`**
  - `MessageResponse(message: str)`
  - `CursorPaginationMeta(next_cursor: str | None, has_more: bool)`

- **`thread.py`**
  - `ThreadCreate(title: str, content: str)`
  - `ThreadUpdate(title: str | None, content: str | None)` — partial update
  - `ThreadResponse(id, title, content, author: UserSnapResponse, status, like_count, comment_count, is_liked: bool, created_at, updated_at)`
  - `ThreadListResponse(threads: list[ThreadResponse], pagination: CursorPaginationMeta)`

- **`comment.py`**
  - `CommentCreate(thread_id: UUID, parent_comment_id: UUID | None, content: str)`
  - `CommentUpdate(content: str | None)`
  - `CommentResponse(id, thread_id, parent_comment_id, author: UserSnapResponse, content, status, like_count, reply_count, is_liked: bool, created_at)`
  - `CommentListResponse(comments: list[CommentResponse], pagination: CursorPaginationMeta)`

- **`like.py`**
  - `LikeResponse(like_count: int, liked: bool)`

- **`user_snap.py`**
  - `UserSnapCreate(user_id: UUID, username: str, avatar_url: str | None)`
  - `UserSnapUpdate(username: str | None, avatar_url: str | None)`
  - `UserSnapResponse(user_id, username, avatar_url, updated_at)`

- **`__init__.py`** — Re-exports all schema classes

---

## Step 6 — Repositories (`app/repositories/`)

### Files

| Action | Path |
|--------|------|
| CREATE | `services/thread/app/repositories/__init__.py` |
| CREATE | `services/thread/app/repositories/seed.py` |
| CREATE | `services/thread/app/repositories/thread_repo.py` |
| CREATE | `services/thread/app/repositories/comment_repo.py` |
| CREATE | `services/thread/app/repositories/like_repo.py` |
| CREATE | `services/thread/app/repositories/user_snap_repo.py` |

### Details

> Pattern: pure data access functions, `AsyncSession` as first param, return ORM models or `None`. *(Reference: `services/user/app/repositories/user_repo.py`)*

- **`seed.py`**
  - `seed_entity_statuses(db)` — Inserts `ACTIVE`, `USER_DELETED`, `MOD_REMOVED` into `entity_status` table if not already present (run on startup)

- **`thread_repo.py`**
  - `create_thread(db, author_id, title, content, status_id) → Thread`
  - `get_thread_by_id(db, thread_id) → Thread | None`
  - `list_threads(db, cursor: datetime | None, limit: int) → list[Thread]` — cursor-based, ACTIVE only, newest first
  - `update_thread(db, thread, **fields) → Thread` — COALESCE update on title/content
  - `soft_delete_thread(db, thread, status_id, deleted_at) → Thread`
  - `increment_comment_count(db, thread_id)`
  - `decrement_comment_count(db, thread_id)`

- **`comment_repo.py`**
  - `create_comment(db, thread_id, author_id, content, status_id, parent_comment_id?) → Comment`
  - `get_comment_by_id(db, comment_id) → Comment | None`
  - `list_top_level_comments(db, thread_id, cursor?, limit) → list[Comment]` — `parent_comment_id IS NULL`, exclude MOD_REMOVED
  - `list_replies(db, parent_comment_id, cursor?, limit) → list[Comment]` — ASC order
  - `update_comment(db, comment, **fields) → Comment`
  - `soft_delete_comment(db, comment, status_id, deleted_at) → Comment`
  - `increment_reply_count(db, parent_comment_id)`
  - `decrement_reply_count(db, parent_comment_id)`

- **`like_repo.py`**
  - `like_thread(db, user_id, thread_id) → ThreadLike` — insert + increment `thread.like_count`
  - `unlike_thread(db, user_id, thread_id)` — delete + decrement `thread.like_count`
  - `has_user_liked_thread(db, user_id, thread_id) → bool`
  - `like_comment(db, user_id, comment_id) → CommentLike` — insert + increment `comment.like_count`
  - `unlike_comment(db, user_id, comment_id)` — delete + decrement `comment.like_count`
  - `has_user_liked_comment(db, user_id, comment_id) → bool`

- **`user_snap_repo.py`**
  - `upsert_user_snap(db, user_id, username, avatar_url?) → UserSnap`
  - `get_user_snap(db, user_id) → UserSnap | None`
  - `delete_user_snap(db, user_id)`

---

## Step 7 — Service Layer (`app/services/`)

### Files

| Action | Path |
|--------|------|
| CREATE | `services/thread/app/services/__init__.py` |
| CREATE | `services/thread/app/services/thread_service.py` |
| CREATE | `services/thread/app/services/comment_service.py` |
| CREATE | `services/thread/app/services/like_service.py` |
| CREATE | `services/thread/app/services/user_snap_service.py` |

### Details

> Pattern: receives `AsyncSession`, calls repositories, raises domain exceptions, enforces authorization. *(Reference: `services/user/app/services/auth_service.py`)*

- **`thread_service.py`**
  - `create_thread(db, user_id, data: ThreadCreate) → Thread`
  - `update_thread(db, user_id, thread_id, data: ThreadUpdate) → Thread` — author-only check, raise `NotAuthorizedError`
  - `delete_thread(db, user_id, role, thread_id) → Thread` — author → USER_DELETED; MODERATOR/ADMIN → MOD_REMOVED; else → `NotAuthorizedError`
  - `get_thread(db, thread_id, user_id?, role?) → ThreadResponse` — apply deletion visibility rules (§9 of LLD)
  - `list_threads(db, cursor, limit) → (list[Thread], CursorPaginationMeta)` — ACTIVE only, cursor-based

  **Deletion visibility rules (§9):**
  | Status | Visible | Content | Children |
  |--------|---------|---------|----------|
  | ACTIVE | ✅ | Normal | Visible |
  | USER_DELETED | ✅ | `[deleted]` | Visible |
  | MOD_REMOVED | ❌ (mods/admins only) | Hidden | Hidden |

- **`comment_service.py`**
  - `create_comment(db, user_id, data: CommentCreate) → Comment` — also increments `thread.comment_count` and `parent.reply_count`
  - `update_comment(db, user_id, comment_id, data: CommentUpdate) → Comment` — author-only
  - `delete_comment(db, user_id, role, comment_id) → Comment` — soft-delete with status + `deleted_at`
  - `get_comments_for_thread(db, thread_id, cursor?, limit) → (list[Comment], meta)` — top-level, exclude MOD_REMOVED
  - `get_replies(db, parent_comment_id, cursor?, limit) → (list[Comment], meta)` — ASC order

- **`like_service.py`**
  - `like_thread(db, user_id, thread_id) → LikeResponse` — check duplicate → `AlreadyLikedError`
  - `unlike_thread(db, user_id, thread_id) → LikeResponse` — check exists → `NotLikedError`
  - `like_comment(db, user_id, comment_id) → LikeResponse` — check duplicate → `AlreadyLikedError`
  - `unlike_comment(db, user_id, comment_id) → LikeResponse` — check exists → `NotLikedError`

- **`user_snap_service.py`**
  - `create_or_update_snap(db, data: UserSnapCreate) → UserSnap`
  - `get_snap(db, user_id) → UserSnap`

---

## Step 8 — API Dependencies & Auth (`app/api/`)

### Files

| Action | Path |
|--------|------|
| CREATE | `services/thread/app/api/__init__.py` |
| CREATE | `services/thread/app/api/deps.py` |
| CREATE | `services/thread/app/api/v1/__init__.py` |

### Details

- **`deps.py`** — Lightweight auth dependency (no DB lookup per §3 of LLD):
  - `get_current_user(credentials=Depends(HTTPBearer()), db=Depends(get_db)) → dict`
  - Extracts JWT from `Authorization: Bearer <token>` header
  - Calls `decode_access_token(token)` from `utils/token.py`
  - Returns `{"user_id": UUID, "role": str}` (no DB user lookup)
  - Raises `InvalidAccessTokenError` on failure

  **Authorization logic (§3.2):**
  ```
  if role == ADMIN or MODERATOR → allow
  else if entity.author_id == user_id → allow
  else → deny (NotAuthorizedError)
  ```

- **`api/__init__.py`** — Empty or minimal
- **`api/v1/__init__.py`** — Creates `router = APIRouter()`, includes all route modules: `threads`, `comments`, `user_snaps`

---

## Step 9 — API Routes (`app/api/v1/`)

### Files

| Action | Path |
|--------|------|
| CREATE | `services/thread/app/api/v1/threads.py` |
| CREATE | `services/thread/app/api/v1/comments.py` |
| CREATE | `services/thread/app/api/v1/user_snaps.py` |

### Details

- **`threads.py`** — Thread + Thread-Like endpoints:
  | Method | Endpoint | Auth | Description |
  |--------|----------|------|-------------|
  | `POST` | `/threads` | ✅ | Create a new thread |
  | `GET` | `/threads` | ❌ | List threads (cursor-based: `?cursor=<timestamp>&limit=10`) |
  | `GET` | `/threads/{id}` | ❌ | Get thread with top-level comments |
  | `PATCH` | `/threads/{id}` | ✅ | Update thread (author only) |
  | `DELETE` | `/threads/{id}` | ✅ | Soft-delete thread (author/mod/admin) |
  | `POST` | `/threads/{id}/like` | ✅ | Like a thread |
  | `DELETE` | `/threads/{id}/like` | ✅ | Unlike a thread |

- **`comments.py`** — Comment + Comment-Like endpoints:
  | Method | Endpoint | Auth | Description |
  |--------|----------|------|-------------|
  | `POST` | `/comments` | ✅ | Create a comment (top-level or reply) |
  | `PATCH` | `/comments/{id}` | ✅ | Update comment (author only) |
  | `DELETE` | `/comments/{id}` | ✅ | Soft-delete comment (author/mod/admin) |
  | `GET` | `/comments?parent_id={id}` | ❌ | Get replies (lazy-loaded, ASC order) |
  | `POST` | `/comments/{id}/like` | ✅ | Like a comment |
  | `DELETE` | `/comments/{id}/like` | ✅ | Unlike a comment |

- **`user_snaps.py`** — Temporary testing endpoints (future: event-driven):
  | Method | Endpoint | Auth | Description |
  |--------|----------|------|-------------|
  | `POST` | `/user-snaps` | ✅ | Create/update a user snapshot |
  | `GET` | `/user-snaps/{user_id}` | ❌ | Get a user snapshot |
  | `PATCH` | `/user-snaps/{user_id}` | ✅ | Update a user snapshot |

---

## Step 10 — Application Entry Point & Wiring

### Files

| Action | Path |
|--------|------|
| UPDATE | `services/thread/app/main.py` |
| CREATE | `services/thread/app/__init__.py` |

### Details

- **`main.py`** — FastAPI application entry point *(Reference: `services/user/app/main.py`)*:
  - Call `configure_logging()` at module level
  - `lifespan` async context manager:
    - `Base.metadata.create_all` (create all tables)
    - `seed_entity_statuses(db)` (seed ACTIVE / USER_DELETED / MOD_REMOVED)
    - Yield
    - `engine.dispose()` on shutdown
  - `FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)`
  - Exception handlers:
    - `RequestValidationError` → 422 JSON
    - `AppException` → custom status code + detail
    - Generic `Exception` → 500
  - Mount router: `app.include_router(v1_router, prefix="/api/v1")`
  - Health check: `GET /health → {"status": "ok"}`

- **`__init__.py`** — Empty init file for the `app` package

---

## Final Directory Tree

```
services/thread/
├── .env
├── pyproject.toml
├── docs/
│   ├── implementation_guide.md
│   └── EXECUTION_PLAN.md
└── app/
    ├── __init__.py
    ├── main.py
    ├── core/
    │   ├── __init__.py
    │   ├── config.py
    │   ├── database.py
    │   ├── exceptions.py
    │   └── logging.py
    ├── utils/
    │   ├── __init__.py
    │   ├── constants.py
    │   └── token.py
    ├── models/
    │   ├── __init__.py
    │   ├── entity_status.py
    │   ├── thread.py
    │   ├── comment.py
    │   ├── thread_like.py
    │   ├── comment_like.py
    │   └── user_snap.py
    ├── schemas/
    │   ├── __init__.py
    │   ├── common.py
    │   ├── thread.py
    │   ├── comment.py
    │   ├── like.py
    │   └── user_snap.py
    ├── repositories/
    │   ├── __init__.py
    │   ├── seed.py
    │   ├── thread_repo.py
    │   ├── comment_repo.py
    │   ├── like_repo.py
    │   └── user_snap_repo.py
    ├── services/
    │   ├── __init__.py
    │   ├── thread_service.py
    │   ├── comment_service.py
    │   ├── like_service.py
    │   └── user_snap_service.py
    └── api/
        ├── __init__.py
        ├── deps.py
        └── v1/
            ├── __init__.py
            ├── threads.py
            ├── comments.py
            └── user_snaps.py
```

**Total new files: 31** · **Updated files: 3** (`pyproject.toml`, `docker-compose.yml`, `main.py`)
