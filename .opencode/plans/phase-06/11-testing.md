# Phase 6 — Dashboard — Testing & Code Quality

> **Goal**: Ensure frontend builds pass, backend auth works, and all existing tests remain green.
> **AI Agent Instructions**: Create frontend tests, update backend auth tests, verify full stack.

---

## Testing Strategy

| Layer | Tool | Scope |
|-------|------|-------|
| Frontend lint | ESLint + Next.js config | Code quality |
| Frontend build | Next.js (`npm run build`) | Compilation, type errors |
| Backend auth tests | pytest (mocked) | Auth dependency, protected endpoints |
| Backend integration | pytest (real DB) | Auth with live API |
| Existing tests | pytest | No regression (267+ tests) |
| Type checking | mypy strict | Python types (no new errors) |
| Python lint | ruff | Code quality |

---

## Frontend Tests

### Setup
```bash
cd frontend
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom
```

### Test Files
| File | What it tests |
|------|---------------|
| `src/lib/__tests__/api-client.test.ts` | API client request format, auth header, error handling |
| `src/hooks/__tests__/use-websocket.test.ts` | WebSocket connect/disconnect, message parsing |
| `src/components/shared/__tests__/wallet-address.test.tsx` | Truncation, copy functionality |
| `src/components/shared/__tests__/metric-card.test.tsx` | Rendering variants, loading state |
| `src/components/shared/__tests__/data-table.test.tsx` | Pagination, sorting, loading, empty |

---

## Backend Auth Tests

### Update existing test files

#### `app/tests/test_api/test_follow_endpoints.py`
- Add auth header to all requests
- Test: request without auth → 401
- Test: request with invalid key → 401
- Test: request with valid key → 200

#### `app/tests/test_api/test_portfolio_endpoints.py`
- Same auth header pattern as follow tests

#### New: `app/tests/test_api/test_auth.py`
```python
"""Test authentication dependency."""

async def test_public_endpoint_no_auth(client):
    """Leaderboard, markets, categories should not require auth."""
    response = await client.get("/api/v1/leaderboard")
    assert response.status_code == 200

async def test_protected_endpoint_no_auth(client):
    """Follow and portfolio endpoints require auth."""
    response = await client.get("/api/v1/follow")
    assert response.status_code == 401

async def test_protected_endpoint_with_valid_key(client):
    """Valid API key should grant access."""
    response = await client.get(
        "/api/v1/follow",
        headers={"Authorization": "Bearer test-api-key"},
    )
    assert response.status_code == 200

async def test_protected_endpoint_with_invalid_key(client):
    """Invalid API key should return 401."""
    response = await client.get(
        "/api/v1/follow",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401

async def test_cors_headers(client):
    """CORS headers should be present on responses."""
    response = await client.options(
        "/api/v1/leaderboard",
        headers={"Origin": "http://localhost:3000"},
    )
    assert "access-control-allow-origin" in response.headers
```

---

## Pre-Commit Checks

```bash
# Backend
ruff check app/
mypy app/
python -m pytest app/tests/test_api/ -v
python -m pytest app/tests/ -v

# Frontend
cd frontend
npm run lint
npm run build
```

---

## MyPy Strict

No new mypy errors from auth changes. Focus:
- `app/api/dependencies/auth.py` — typed correctly
- `app/api/v1/follow.py` — `user_id: str` from dependency
- `app/api/v1/portfolio.py` — same pattern

---

## Verification Commands

```bash
# 1. Backend lint + types
ruff check app/ && mypy app/ && echo "Backend OK"

# 2. Backend tests
python -m pytest app/tests/ -v && echo "Backend tests OK"

# 3. Frontend lint
cd frontend && npm run lint && echo "Frontend lint OK"

# 4. Frontend build
cd frontend && npm run build && echo "Frontend build OK"

# 5. Integration (requires postgres)
python -m pytest app/tests/test_db_integrity.py -m integration -v && echo "Integration OK"

# 6. Docker compose
docker compose build && echo "Docker build OK"
```

---

## Expected Test Counts

| Suite | Count | Notes |
|-------|-------|-------|
| Existing backend tests | 267 | No regression |
| New auth unit tests | ~5 | `test_auth.py` |
| New auth integration | ~3 | In `test_db_integrity.py` |
| Frontend lint | 0 errors | ESLint |
| Frontend build | 0 errors | Next.js |
| Total | 275+ | |

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `app/tests/test_api/test_auth.py` |
| EDIT | `app/tests/test_api/test_follow_endpoints.py` (add auth headers) |
| EDIT | `app/tests/test_api/test_portfolio_endpoints.py` (add auth headers) |
| CREATE | `frontend/src/lib/__tests__/api-client.test.ts` |
| CREATE | `frontend/src/components/shared/__tests__/wallet-address.test.tsx` |
| CREATE | `frontend/src/components/shared/__tests__/metric-card.test.tsx` |
| CREATE | `frontend/src/components/shared/__tests__/data-table.test.tsx` |

---

## Verification

```bash
python -m pytest app/tests/test_api/test_auth.py -v
# Expected: 5 passed

cd frontend && npm run build
# Expected: 0 errors, 0 warnings

ruff check app/
# Expected: 0 errors (existing + new auth code)
```
