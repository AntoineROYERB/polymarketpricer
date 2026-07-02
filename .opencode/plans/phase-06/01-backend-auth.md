# Phase 6 — Dashboard — Backend Auth

> **Goal**: Add basic API key authentication to the FastAPI backend, replacing the `_USER_ID = "default"` placeholder in Phase 5 endpoints.
> **AI Agent Instructions**: Create an auth dependency, API key model, config, and wire it into `follow.py` and `portfolio.py`. Existing public endpoints remain accessible without auth.

---

## Design Decision: API Key Auth

API key (Bearer token in `Authorization` header) stored in DB or config. Simple, stateless, sufficient for single-user/multi-user without OAuth complexity.

- **POST `/api/v1/auth/login`** — accepts API key, returns a signed JWT or just sets session
- **OR simpler**: static API key from `.env` → frontend stores in `Authorization: Bearer <key>` header

For a pragmatic MVP: **static API key via `.env`**. The frontend sends `Authorization: Bearer <API_KEY>` on all requests. Backend validates via a dependency. This avoids JWT complexity and a login endpoint.

If multi-user is needed later, the same middleware can validate against a DB table.

---

## Files to Modify

### `.env` (root)
```
API_KEY=devkey-change-me
```

### `app/config.py`
```python
api_key: str = "devkey-change-me"
```

### New: `app/api/dependencies/auth.py`
```python
from fastapi import Header, HTTPException, status
from app.config import settings


async def require_api_key(x_api_key: str = Header(alias="Authorization")):
    """Require a valid API key. Expects 'Bearer <token>' format."""
    if not x_api_key or not x_api_key.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    token = x_api_key.removeprefix("Bearer ")
    if token != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return True


async def optional_api_key(x_api_key: str = Header(None, alias="Authorization")):
    """Optional auth — returns user_id or 'default'."""
    if x_api_key and x_api_key.startswith("Bearer "):
        token = x_api_key.removeprefix("Bearer ")
        if token == settings.api_key:
            return "user"  # future: look up real user_id
    return "default"
```

### `app/api/v1/follow.py`
- Replace `_USER_ID = "default"` with `user_id: str = Depends(optional_api_key)`
- All route functions accept `user_id` parameter

### `app/api/v1/portfolio.py`
- Same pattern: replace `_USER_ID = "default"` with `user_id: str = Depends(optional_api_key)`

### `app/api/v1/alerts.py` (WebSocket)
- WebSocket endpoint should accept auth via query param or first message
- Add `api_key` query param to `GET /api/v1/alerts/ws`

### `app/main.py`
- Update CORS to allow frontend origin (`cors_origins` from settings)

### `app/api/router.py`
- Add auth router if login endpoint is created

---

## Auth Flow

```
Frontend App                    Backend API
    │                               │
    │  GET /api/v1/leaderboard       │
    │  (no auth header)              │  ← public endpoint
    │                               │
    │  GET /api/v1/follow            │
    │  Authorization: Bearer key123  │  ← protected endpoint
    │                               │
    │  If 401 → redirect to login    │
```

---

## Verification

```bash
# Public endpoint — no auth needed
curl http://localhost:8000/api/v1/leaderboard

# Protected endpoint — 401 without key
curl -i http://localhost:8000/api/v1/follow
# Expected: 401

# Protected endpoint — 200 with key
curl -i -H "Authorization: Bearer devkey-change-me" \
  http://localhost:8000/api/v1/follow
# Expected: 200

# Backward compat — default key still works as published
```
