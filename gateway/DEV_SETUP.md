# Nginx Dev Gateway Setup

This guide explains how to run the Nginx API gateway locally when developing
without Docker — both services run directly on `localhost` and nginx forwards
requests to them.

---

## How it works

```
Your HTTP client  (curl / Postman / browser)
        │
        ▼
  Nginx  :8080          ← single entry point
        │
        ├── /api/v1/auth/*        ──►  localhost:8000  (user-service)
        ├── /api/v1/users/*       ──►  localhost:8000  (user-service)
        │
        ├── /api/v1/threads/*     ──►  localhost:8001  (thread-service)
        ├── /api/v1/comments/*    ──►  localhost:8001  (thread-service)
        └── /api/v1/user-snaps/*  ──►  localhost:8001  (thread-service)
```

The dev config (`nginx.dev.conf`) is identical to the production config
(`nginx.conf`) except:

| | `nginx.dev.conf` | `nginx.conf` |
|---|---|---|
| Upstream hosts | `127.0.0.1:8000 / :8001` | `user-service:8000 / thread-service:8001` (Docker DNS) |
| Listen port | `8080` (no sudo needed) | `80` |

---

## Prerequisites

Install nginx if you don't have it:

```bash
# Ubuntu / Debian
sudo apt install nginx

# macOS
brew install nginx
```

---

## Step-by-step startup

Open **three terminals** in the project root
(`/home/ramsantoshraut/projects/threadify/server`):

### Terminal 1 — User service

```bash
cd services/user
uvicorn app.main:app --port 8000 --reload
```

### Terminal 2 — Thread service

```bash
cd services/thread
uvicorn app.main:app --port 8001 --reload
```

### Terminal 3 — Nginx gateway

```bash
# Validate the config first (always a good habit)
nginx -t -c $(pwd)/gateway/nginx.dev.conf

# Start nginx with the dev config
nginx -c $(pwd)/gateway/nginx.dev.conf
```

> **Important:** `-c` requires an **absolute path**.  
> `$(pwd)/gateway/nginx.dev.conf` expands to the absolute path automatically
> as long as you run the command from the project root.

---

## Verify everything is running

```bash
# Gateway itself
curl http://localhost:8080/health
# → {"status":"ok","service":"gateway","env":"dev"}

# User service (proxied through nginx)
curl http://localhost:8080/health/user
# → {"status":"ok"}

# Thread service (proxied through nginx)
curl http://localhost:8080/health/thread
# → {"status":"ok"}
```

All your API calls now go through `http://localhost:8080` and nginx routes
them to the correct service automatically.

---

## Stop nginx

```bash
nginx -s stop
```

Or gracefully drain in-flight requests first:

```bash
nginx -s quit
```

---

## Reload config without restarting (after editing `nginx.dev.conf`)

```bash
nginx -s reload
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `nginx: [emerg] bind() to 0.0.0.0:8080 failed` | Port already in use | `lsof -i :8080` then kill the process |
| `502 Bad Gateway` | The target service isn't running | Start the service in its terminal |
| `nginx: [emerg] open() "…/nginx.dev.conf" failed` | Relative path given to `-c` | Use the absolute path: `nginx -c $(pwd)/gateway/nginx.dev.conf` |
| Config test fails | Syntax error in conf | Run `nginx -t -c $(pwd)/gateway/nginx.dev.conf` and read the error line |
