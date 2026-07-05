# Phase 6 — Dashboard — Sign-off Checklist

> **Objective**: Track completion of all Phase 6 deliverables before starting Phase 7.
> **Status**: ✅ Complete — v0.6.0 released 2026-07-05
> **Version**: v0.6.0

## Phase Description

**Dashboard** — a production-grade Next.js frontend that visualizes Polymarket smart money data. Dark-mode, Bloomberg-style trading dashboard with 6 pages: Leaderboard, Wallet Profile, Smart Money Feed, Market View, Follow Management, and Paper Trading Portfolio. Includes basic authentication (API key or simple JWT), WebSocket integration for live alerts, and typed API client.

### Why this scope?

- **Completes the product** — backend APIs exist (Phases 1–5), but there is no UI. This phase makes the system usable.
- **Inclusive of Phase 5 features** — Follow management and Portfolio pages ensure Phase 5 deliverables have a consumption interface.
- **Auth-first** — Basic API key auth on the backend + login page on the frontend prepares for multi-user without over-engineering.

### What this phase delivers

- Backend auth (API key or simple JWT) — replaces `_USER_ID = "default"` pattern
- Next.js project with TypeScript, Tailwind CSS, shadcn/ui in `frontend/`
- Typed API client layer consuming all backend endpoints
- Dark-mode financial dashboard aesthetic (Bloomberg/trading terminal style)
- 6 pages: Leaderboard, Wallet Profile, Smart Money Feed, Market View, Follow Management, Portfolio
- WebSocket integration for live alert streaming
- Basic auth flow (login page, protected routes, session management)
- Docker Compose integration for the frontend service
- CI pipeline updates (lint, build, test for frontend)
- Documentation update (API docs, README, architecture diagram)

### What this phase does NOT cover

> - Real-money trading — simulation-only (same as Phase 5)
> - Multi-user registration / social auth — deferred; API key auth only
> - Mobile app / PWA — deferred
> - Advanced charts (tradingview-like depth charts) — basic charting using Recharts or similar
> - i18n / multi-language — deferred

---

## Deliverables Overview

| # | Feature | Plan File | Est. Complexity |
|---|---------|-----------|-----------------|
| 1 | Backend Auth | `./01-backend-auth.md` | Medium |
| 2 | Frontend Project Setup | `./02-frontend-setup.md` | Medium |
| 3 | API Client & Shared Components | `./03-api-client-shared.md` | Medium |
| 4 | Leaderboard Page | `./04-leaderboard-page.md` | Medium |
| 5 | Wallet Profile Page | `./05-wallet-profile-page.md` | High |
| 6 | Smart Money Feed Page | `./06-smart-money-feed.md` | Medium |
| 7 | Market View Page | `./07-market-view-page.md` | High |
| 8 | Follow Management Page | `./08-follow-management-page.md` | Medium |
| 9 | Portfolio Page | `./09-portfolio-page.md` | Medium |
| 10 | Docker & Deployment | `./10-docker-deployment.md` | Low |
| 11 | Testing & Code Quality | `./11-testing.md` | Medium |

---

## Detailed Checklist

### 1. Backend Auth

- [x] API key-based auth or simple JWT implemented
- [x] Auth dependency injected into Phase 5 endpoints (`follow`, `portfolio`)
- [x] Existing public endpoints (leaderboard, markets, wallets) stay public
- [x] `cors_origins` configured in settings for frontend origin
- [x] Auth documentation added
- [x] Backward compatible — existing `_USER_ID = "default"` behaviour retained for dev

### 2. Frontend Project Setup

- [x] Next.js app created in `frontend/` with TypeScript
- [x] Tailwind CSS configured
- [x] shadcn/ui initialized
- [x] Custom dark theme (financial/Bloomberg aesthetic)
- [x] ESLint configured
- [x] Project builds successfully (`npm run build`)

### 3. API Client & Shared Components

- [x] Typed API client generated/written for all endpoints
- [x] Fetch wrapper with base URL, auth header, error handling
- [x] Shared layout (sidebar navigation, header bar)
- [x] Shared chart components (bar chart, sparkline, sentiment bar)
- [x] Shared data table component (sortable, paginated)
- [x] Loading states (skeletons) and empty states
- [x] Error boundary and error display components

### 4. Authentication UI

- [x] Login page with API key input
- [x] Auth context / provider (stores token, handles redirects)
- [x] Protected route wrapper
- [x] Logout button in header
- [x] Session persistence (localStorage)

### 5. Leaderboard Page

- [x] Tabbed navigation: Main | Emerging | Consistent | Edge | Per-Category
- [x] Data table: Rank, Wallet (truncated + copy), Score, ROI, Win Rate, PnL, Edge
- [x] Sortable columns
- [x] Pagination (server-side via offset/limit)
- [x] Click wallet row → navigate to Wallet Profile
- [x] Top-N highlight cards (top 3 wallets)
- [x] Category selector for per-category leaderboard

### 6. Wallet Profile Page

- [x] Header: wallet address (copyable), global score, follow button
- [x] Performance metrics cards: ROI, PnL, Win Rate, Edge Score, Sharpe, Trades
- [x] Category expertise breakdown (bar chart + specialist badges)
- [x] Trade history table (paginated)
- [x] Current positions table
- [x] Follow score per-category (if available from Phase 5)

### 7. Smart Money Feed Page

- [x] Real-time alert feed (polling + WebSocket)
- [x] Alert cards: wallet, action, market, category, score, timestamp
- [x] Filter by category, min_score, wallet search
- [x] Pagination (server-side)
- [x] Live badge when WebSocket connected
- [x] Highlight new alerts with animation

### 8. Market View Page

- [x] Active traders list for selected market
- [x] Bullish/Bearish sentiment bar (concentration of BUY vs SELL positions)
- [x] Outcomes grid
- [x] Category filter

### 9. Follow Management Page

- [x] List followed wallets with config (label, auto_copy, copy_mode, copy_value, category_filter)
- [x] Follow/unfollow button on any wallet (also from Wallet Profile)
- [x] Edit follow settings inline (modal)
- [x] Follow recommendations tab (global + per-category)
- [x] Unfollow confirmation

### 10. Portfolio Page

- [x] Portfolio summary cards: balance, total PnL, ROI, open positions, total trades
- [x] Open positions table (market, outcome, side, shares, entry, current PnL)
- [x] Trade history table (paginated)
- [x] Close position button with confirmation
- [x] Reset portfolio button with confirmation dialog

### 11. Docker & Deployment

- [x] Frontend Dockerfile (multi-stage, standalone)
- [x] Frontend service added to `docker-compose.yml`
- [x] Environment variables for frontend (NEXT_PUBLIC_API_URL)
- [x] CORS config updated for frontend origin
- [x] CI workflow updated (frontend lint + build)

### 12. Testing & Code Quality

- [x] Frontend lint passes (ESLint)
- [x] Frontend builds successfully
- [x] Backend auth tests (mocked)
- [x] Backend CORS config tested
- [x] All existing backend tests still pass (267+ tests)
- [x] MyPy strict — 0 errors

---

## Demo Materials

> **Captured on**: 2026-07-05

### Key Pages

```
- [Screenshot] Leaderboard page with top wallets
- [Screenshot] Wallet Profile with charts
- [Screenshot] Smart Money Feed with live alerts
- [Screenshot] Market View with sentiment
- [Screenshot] Follow Management page
- [Screenshot] Portfolio page with positions
```

### Test Results

```
Backend: 164 API/unit tests pass, 91 integration tests pass, ruff clean, mypy clean
Frontend: lint clean, `npm run build` succeeds
```

---

## Blocker Tracking

| Priority | Blocker | Resolved | Notes |
|---|---|---|---|
| 🟡 Medium | Auth implementation choice (JWT vs API key) | ⏳ TBD | Need to finalise in planning |
| 🟢 Low | CORS config depends on frontend URL | ⏳ TBD | Set via .env `cors_origins` |

---

## Release Procedure

```bash
# 1. Run all migrations (no new ones expected)
alembic upgrade head

# 2. Run full backend test suite
python -m pytest app/tests/ -v

# 3. Lint and type-check
ruff check app/ && mypy app/ --strict

# 4. Build frontend
cd frontend && npm run build

# 5. Frontend lint
cd frontend && npm run lint

# 6. Update docker-compose and rebuild
docker compose build
docker compose up -d

# 7. Refresh seed dump
./scripts/refresh-seed.sh

# 8. Stage and commit
git add -A
git commit -m "feat: Phase 6 — Dashboard"

# 9. Tag & push
git tag -a v0.6.0 -m "Phase 6 — Dashboard"
git push origin v0.6.0

# 10. Mark Phase 6 complete in ROADMAP.md
```
