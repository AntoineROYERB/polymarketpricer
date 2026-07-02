# Phase 6 — Dashboard — Docker & Deployment

> **Goal**: Containerize the frontend and integrate it into the Docker Compose stack. Update CI and docs.
> **AI Agent Instructions**: Create `frontend/Dockerfile`, add frontend service to `docker-compose.yml`, update `.env` and CI workflow.

---

## Frontend Dockerfile (`frontend/Dockerfile`)

Multi-stage build: Next.js standalone output served via Node.js or nginx.

```Dockerfile
# Stage 1: Dependencies + Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Production
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

---

## Docker Compose Service (`docker-compose.yml`)

Add frontend service alongside existing postgres, mage, app:

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
    target: runner
  ports:
    - "3000:3000"
  environment:
    - NEXT_PUBLIC_API_URL=http://app:8000/api/v1
    - NEXT_PUBLIC_WS_URL=ws://app:8000/api/v1/alerts/ws
  env_file:
    - .env
  depends_on:
    - app
  restart: unless-stopped
```

### Backend CORS Update (`app/config.py`)

```python
cors_origins: list[str] = ["http://localhost:3000"]  # default dev
```

Overridable via `.env`:
```
CORS_ORIGINS='["http://localhost:3000","https://dashboard.example.com"]'
```

---

## Environment Variables

### `.env` (root — shared across services)

Additions:
```
# Frontend (used in docker-compose environment)
NEXT_PUBLIC_API_URL=http://app:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://app:8000/api/v1/alerts/ws

# Auth
API_KEY=devkey-change-me
```

### `frontend/.env.local` (development — not committed)

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/alerts/ws
```

---

## CI Update (`.github/workflows/ci.yml`)

Add a frontend job:

```yaml
frontend-checks:
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: ./frontend
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: "npm"
        cache-dependency-path: frontend/package-lock.json
    - run: npm ci
    - run: npm run lint
    - run: npm run build
```

---

## Docker Compose Dev Experience

```bash
# Start all services (frontend included)
docker compose up -d

# Frontend at http://localhost:3000
# API at http://localhost:8000
# Docs at http://localhost:8000/docs

# Or run frontend locally for hot reload:
cd frontend && npm run dev
# API_URL = http://localhost:8000
```

---

## .dockerignore (`frontend/.dockerignore`)

```
node_modules
.next
.git
*.md
.env.local
.env*.local
```

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `frontend/Dockerfile` |
| CREATE | `frontend/.dockerignore` |
| EDIT | `docker-compose.yml` (add frontend service) |
| EDIT | `app/config.py` (update `cors_origins` default) |
| EDIT | `.env` (add frontend URLs + API_KEY) |
| EDIT | `.github/workflows/ci.yml` (add frontend job) |

---

## Verification

```bash
docker compose build frontend   # Build succeeds
docker compose up -d            # All services start
curl http://localhost:3000      # Returns HTML
curl http://localhost:8000/api/v1/leaderboard  # API still works
```
