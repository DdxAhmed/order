# Docker & Container Architecture — OrderTrofy

## 1. Overview

The project provides complete containerization for reproducible local development and production deployments:
- **`compose.yaml`**: Full multi-service production stack (PostgreSQL, FastAPI Backend, Steam Worker, React Frontend, and Caddy Reverse Proxy).
- **`compose.dev.yaml`**: Local development overrides binding services strictly to `127.0.0.1` loopback ports.

---

## 2. Port Architecture (Host vs. Container)

| Service | Container Internal Port | Local Development Host Port | Production Host Port | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`postgres`** | `5432` | `127.0.0.1:5433` | Not exposed publicly | Host port 5433 avoids Windows TCP reserved ranges |
| **`web`** | `8000` | `127.0.0.1:8000` | Reverse-proxied via Caddy | FastAPI Uvicorn application |
| **`frontend`** | `80` | `127.0.0.1:5173` | Reverse-proxied via Caddy | Caddy serving static SPA with `/index.html` fallback |
| **`caddy`** | `80`, `443` | N/A (Optional) | `80:80`, `443:443` | TLS termination & domain routing |

---

## 3. Container Images & Build Hardening

### 3.1 Backend Image (`Dockerfile` / `backend/Dockerfile`)
- **Base:** `python:3.12-slim`
- **Security:** Non-root execution under system user `app:app`.
- **Dependencies:** Deterministic locked installation using `pip install --no-cache-dir -r requirements.lock`.
- **Healthcheck:**
  ```dockerfile
  HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
  ```
- **Binding:** Binds explicitly to `0.0.0.0:8000` with `--proxy-headers`.

### 3.2 Frontend Image (`frontend/Dockerfile`)
- **Stage 1 (Build):** `node:22-alpine` runs `npm ci` and `npm run build`.
- **Stage 2 (Runtime):** Lightweight `caddy:2.8-alpine` serves `/srv` with:
  ```caddyfile
  :80 {
      root * /srv
      encode gzip zstd
      try_files {path} /index.html
      file_server
  }
  ```
- **SPA Fallback:** Guarantees that refreshing or directly opening `/admin/orders` or `/admin/login` renders `index.html` without returning HTTP 404.

---

## 4. Useful Docker Commands

### Start Full Local Development Stack
```powershell
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
```

### Check Running Containers & Health
```powershell
docker compose ps
```

### Inspect Container Logs
```powershell
# Web backend logs
docker compose logs -f web

# Steam OTP worker logs
docker compose logs -f worker

# Frontend logs
docker compose logs -f frontend
```

### Run Migrations Inside Container
```powershell
docker compose exec web python -m alembic upgrade head
```

### Graceful Shutdown
```powershell
docker compose down
```
*(Note: Named volume `postgres_data` persists across container restarts).*
