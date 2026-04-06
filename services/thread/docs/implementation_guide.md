# ========================================

# 1. OVERVIEW

# ========================================

The Thread & Comment Service is responsible for:

* Creating and managing discussion threads
* Supporting multi-level nested comments
* Handling likes on threads and comments
* Supporting moderation (user deletion + mod removal)
* Providing paginated access to threads and comments
* Using JWT-based authentication for authorization
* Using denormalized user data via `user_snap`
* Data will be filled into the `user_snap` via event driven interservice communication , for now keep api's for testing 

---

# ========================================

# 2. CORE REQUIREMENTS

# ========================================

---

## Threads

* Users can create threads
* Users can edit their own threads
* Users can delete their own threads
* Moderators/Admins can delete any thread
* Threads support likes
* Threads are paginated (latest first)

---

## Comments

* Users can create comments (nested)
* Users can edit their own comments
* Users can delete their own comments
* Moderators/Admins can delete any comment
* Supports multi-level nesting
* Lazy loading of replies
* Comments support likes

---

## Likes

* A user can like a thread/comment only once
* Like count stored in main tables


---

# ========================================

# 3. AUTHENTICATION FLOW

# ========================================

---
* Refer the user service for the config.py , the logger.py and how the env variables are loaded , follow a similar flow  
* have constants.py , a config.py , a logger.py and .env too with all the important settings and flow (REFER the user service)

## 3.1 JWT Handling

* Each request contains JWT
* Service verifies token using public key
* public is stored in the .env file , load the settings using config 
* Extracts:

```json id="auth1"
{
  "user_id": 123,
  "role": "USER" | "MODERATOR" | "ADMIN"
}
* have a constants.py file and load the all the constants in that , adn other important things in the .env file 

```

---

## 3.2 Authorization

* No DB lookup required for role
* Role is used directly from JWT

```pseudo id="auth2"
if role == ADMIN or MODERATOR:
    allow
else if entity.author_id == user_id:
    allow
else:
    deny
```

---

## 3.3 User Snapshot

```sql id="usnap_final"
user_snap {
  user_id BIGINT [primary key]
  username VARCHAR
  avatar_url TEXT
  updated_at TIMESTAMP
}
```

👉 Used only for display purposes

---

# ========================================

# 4. DATABASE DESIGN

# ========================================

---

## 📌 4.1 Threads
*instead of the status ENUM , have a separate table for it, allowing scope for additional fields in the future 

```sql id="threads_final"
threads {
  id BIGINT [primary key]

  title TEXT
  content TEXT

  author_id BIGINT

  status ENUM (
    ACTIVE,
    USER_DELETED,
    MOD_REMOVED
  )

  deleted_at TIMESTAMP NULL

  like_count INT DEFAULT 0
  comment_count INT DEFAULT 0

  created_at TIMESTAMP
  updated_at TIMESTAMP
}
```

---

## 📌 4.2 Comments

```sql id="comments_final"
comments {
  id BIGINT [primary key]

  post_id BIGINT
  parent_comment_id BIGINT NULL

  author_id BIGINT
  content TEXT

  status ENUM (
    ACTIVE,
    USER_DELETED,
    MOD_REMOVED
  )

  deleted_at TIMESTAMP NULL

  like_count INT DEFAULT 0
  reply_count INT DEFAULT 0

  created_at TIMESTAMP
}
```

---

## 📌 4.3 Thread Likes

```sql id="threadlikes_final"
thread_likes {
  id BIGINT [primary key]

  user_id BIGINT
  thread_id BIGINT

  created_at TIMESTAMP

  UNIQUE(user_id, thread_id)
}
```

---

## 📌 4.4 Comment Likes

```sql id="commentlikes_final"
comment_likes {
  id BIGINT [primary key]

  user_id BIGINT
  comment_id BIGINT

  created_at TIMESTAMP

  UNIQUE(user_id, comment_id)
}
```

---

# ========================================

# 5. THREAD APIs & FLOWS

# ========================================

---

## 5.1 CREATE THREAD

```http
POST /threads
```

Flow:

1. Extract user_id
2. Insert thread

```sql
INSERT INTO threads (title, content, author_id)
VALUES (:title, :content, :user_id);
```

---

## 5.2 UPDATE THREAD

```http
PATCH /threads/{id}
```

* Only author allowed

```sql
UPDATE threads
SET title = COALESCE(:title, title),
    content = COALESCE(:content, content),
    updated_at = NOW()
WHERE id = :id AND author_id = :user_id;
```

---

## 5.3 DELETE THREAD

```http
DELETE /threads/{id}
```

Flow:

* If author → USER_DELETED
* If mod/admin → MOD_REMOVED

```sql
UPDATE threads
SET status = :status,
    deleted_at = NOW()
WHERE id = :id;
```

---

# ========================================

# 6. COMMENT APIs & FLOWS

# ========================================

---

## 6.1 CREATE COMMENT

```http
POST /comments
```

```sql
INSERT INTO comments (post_id, parent_comment_id, content, author_id)
VALUES (:post_id, :parent_id, :content, :user_id);
```

Update counters:

```sql
UPDATE threads SET comment_count = comment_count + 1 WHERE id = :post_id;

UPDATE comments SET reply_count = reply_count + 1 WHERE id = :parent_id;
```

---

## 6.2 UPDATE COMMENT

```http
PATCH /comments/{id}
```

```sql
UPDATE comments
SET content = :content
WHERE id = :id AND author_id = :user_id;
```

---

## 6.3 DELETE COMMENT

```http
DELETE /comments/{id}
```

```sql
UPDATE comments
SET status = :status,
    deleted_at = NOW()
WHERE id = :id;
```

---

# ========================================

# 7. LIKE APIs & FLOWS

# ========================================

---

## 7.1 LIKE THREAD

```http
POST /threads/{id}/like
```

```sql
INSERT INTO thread_likes(user_id, thread_id);

UPDATE threads
SET like_count = like_count + 1
WHERE id = :thread_id;
```

---

## 7.2 LIKE COMMENT

```http
POST /comments/{id}/like
```

```sql
INSERT INTO comment_likes(user_id, comment_id);

UPDATE comments
SET like_count = like_count + 1
WHERE id = :comment_id;
```

---

## 7.3 UNLIKE (Optional)

```http
DELETE /threads/{id}/like
```

```sql
DELETE FROM thread_likes
WHERE user_id = :user_id AND thread_id = :thread_id;

UPDATE threads
SET like_count = like_count - 1
WHERE id = :thread_id;
```

---

# ========================================

# 8. PAGINATION & FETCHING

# ========================================

---

## 8.1 GET THREADS

```http
GET /threads?cursor=timestamp&limit=10
```

```sql
SELECT *
FROM threads
WHERE created_at < :cursor
AND status = 'ACTIVE'
ORDER BY created_at DESC
LIMIT 10;
```

---

## 8.2 GET THREAD WITH COMMENTS

```http
GET /threads/{id}
```

```sql
SELECT *
FROM comments
WHERE post_id = :id
AND parent_comment_id IS NULL
AND status != 'MOD_REMOVED'
ORDER BY created_at DESC
LIMIT 10;
```

---

## 8.3 GET REPLIES

```http
GET /comments?parent_id=123
```

```sql
SELECT *
FROM comments
WHERE parent_comment_id = :parent_id
AND status != 'MOD_REMOVED'
ORDER BY created_at ASC
LIMIT 10;
```

---

# ========================================

# 9. DELETION BEHAVIOR

# ========================================

---
* in all the cases posts, comments are soft-delted , its just that the mod/admin deleted posts are visible to mods/admins only 

* wehereas user_deleted are visible to everyone with a direct link but the content is rendered as `[deleted]` children , comments are visible yet

*user_deleted posts would not be rendered in the feed 

| Status       | Visible | Content     | Children |
| ------------ | ------- | ----------- | -------- |
| ACTIVE       | ✅       | normal      | visible  |
| USER_DELETED | ✅       | `[deleted]` | visible  |
| MOD_REMOVED  | ❌       | hidden      | hidden   |

---

# ========================================

# 10. DESIGN DECISIONS

# ========================================

---

## ✅ Chosen

* Soft delete with `status`
* JWT-based auth (user_id + role)
* Lazy loading for comments
* Adjacency list for nesting
* Simple like system
* Denormalized `user_snap`
* Cursor-based pagination

---

## ❌ Deferred

* Real-time systems
* Redis caching
* Like scaling optimization
* Hard delete

---

# ========================================

# 11. EXTENSIBILITY

# ========================================

---

Supports future additions:

* WebSockets for real-time
* Redis caching layer
* Like batching / scaling
* Ranking algorithms
* Audit logs

---

# ========================================

# END OF DOCUMENT

# ========================================
