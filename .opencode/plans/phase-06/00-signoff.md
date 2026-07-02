# Phase 6 — Dashboard — Sign-off Checklist

> **Objective**: Track completion of all Phase 6 deliverables before starting Phase 7.
> **Status**: 🚧 In progress
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

- [ ] API key-based auth or simple JWT implemented
- [ ] Auth dependency injected into Phase 5 endpoints (`follow`, `portfolio`)
- [ ] Existing public endpoints (leaderboard, markets, wallets) stay public
- [ ] `cors_origins` configured in settings for frontend origin
- [ ] Auth documentation added
- [ ] Backward compatible — existing `_USER_ID = "default"` behaviour retained for dev

### 2. Frontend Project Setup

- [ ] Next.js app created in `frontend/` with TypeScript
- [ ] Tailwind CSS configured
- [ ] shadcn/ui initialized
- [ ] Custom dark theme (financial/Bloomberg aesthetic)
- [ ] ESLint + Prettier configured
- [ ] Project builds successfully (`npm run build`)

### 3. API Client & Shared Components

- [ ] Typed API client generated/written for all endpoints
- [ ] Axios or fetch wrapper with base URL, auth header, error handling
- [ ] Shared layout (sidebar navigation, header bar)
- [ ] Shared chart components (line chart, bar chart, sparkline)
- [ ] Shared data table component (sortable, paginated)
- [ ] Loading states (skeletons) and empty states
- [ ] Error boundary and error display components

### 4. Authentication UI

- [ ] Login page with API key input
- [ ] Auth context / provider (stores token, handles redirects)
- [ ] Protected route wrapper
- [ ] Logout button in header
- [ ] Session persistence (localStorage or cookies)

### 5. Leaderboard Page

- [ ] Tabbed navigation: Main | Emerging | Consistent | Edge | Per-Category
- [ ] Data table: Rank, Wallet (truncated + copy), Score, ROI, Win Rate, PnL, Edge
- [ ] Sortable columns
- [ ] Pagination (server-side via offset/limit)
- [ ] Click wallet row → navigate to Wallet Profile
- [ ] Top-N highlight cards (top 3 wallets)
- [ ] Category selector for per-category leaderboard

### 6. Wallet Profile Page

- [ ] Header: wallet address (copyable), global score, follow button
- [ ] Performance metrics cards: ROI, PnL, Win Rate, Edge Score, Sharpe, Trades
- [ ] Category expertise breakdown (bar chart + specialist badges)
- [ ] Trade history table (paginated)
- [ ] Current positions table
- [ ] Follow score per-category (if available from Phase 5)

### 7. Smart Money Feed Page

- [ ] Real-time alert feed (polling + WebSocket)
- [ ] Alert cards: wallet, action, market, category, score, timestamp
- [ ] Filter by category, min_score, wallet search
- [ ] Pagination (server-side)
- [ ] Live badge when WebSocket connected
- [ ] Highlight new alerts with animation

### 8. Market View Page

- [ ] Market search/autocomplete
- [ ] Active traders list for selected market
- [ ] Bullish/Bearish sentiment bar (concentration of BUY vs SELL positions)
- [ ] Top positions by size
- [ ] Recent alerts for this market
- [ ] Category filter + date range

### 9. Follow Management Page

- [ ] List followed wallets with config (label, auto_copy, copy_mode, copy_value, category_filter)
- [ ] Follow/unfollow button on any wallet (also from Wallet Profile)
- [ ] Edit follow settings inline (modal or slide panel)
- [ ] Follow recommendations tab (global + per-category)
- [ ] Unfollow confirmation

### 10. Portfolio Page

- [ ] Portfolio summary cards: balance, total PnL, ROI, open positions, total trades
- [ ] Open positions table (market, outcome, side, shares, entry, current PnL)
- [ ] Trade history table (paginated)
- [ ] Close position button with confirmation
- [ ] Reset portfolio button with confirmation dialog

### 11. Docker & Deployment

- [ ] Frontend Dockerfile (multi-stage: build + nginx or standalone)
- [ ] Frontend service added to `docker-compose.yml`
- [ ] Environment variables for frontend (NEXT_PUBLIC_API_URL)
- [ ] CORS config updated for frontend origin
- [ ] CI workflow updated (frontend lint + build)

### 12. Testing & Code Quality

- [ ] Frontend lint passes (ESLint)
- [ ] Frontend builds successfully
- [ ] Backend auth tests (mocked + integration)
- [ ] Backend CORS config tested
- [ ] All existing backend tests still pass (267+ tests)
- [ ] MyPy strict — 0 errors

---

## Demo Materials

> **Captured on**: {date}

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
{all backend tests pass, frontend builds}
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
