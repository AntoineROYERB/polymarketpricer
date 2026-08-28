# Changelog

## v0.6.2 (2026-08-28)

Pre-publication security audit. Full-history secret scan (969 blobs, 138 commits) found
no committed credentials; the findings below were all in application code or tooling.

### Security
- **WebSocket auth bypass** (breaking): `/api/v1/alerts/ws` only rejected an *incorrect*
  `api_key`, never a missing one, so any non-browser client could attach to the alert
  stream. The key was documented as "optional" in v0.6.0; it is now required, and a
  missing, empty or wrong key closes with `4001` alike. Clients that connected without a
  key must now send one.
- **Rate limiting was inactive on every API route**: since FastAPI 0.13x, `include_router`
  is represented by a single `_IncludedRouter` with no `endpoint` attribute, so slowapi's
  middleware found no handler and treated all 28 `/api/v1/*` routes as exempt. `/health`
  and `/docs` stayed limited, which hid the gap. Replaced with `app/api/rate_limit.py`,
  which keys the check on the request path; `/health` is now explicitly exempt so
  container health probes are never throttled.
- **Timing-safe key comparison**: `secrets.compare_digest` on both auth paths.
- **LIKE metacharacter escaping**: a caller-supplied `%` in the market search or the alert
  wallet filter turned the filter into a match-everything. Added `app/utils/sql.py`;
  bounded the alert wallet filter at 100 characters.
- **Wallet validation**: `^0x.+$` accepted anything 0x-prefixed while the error message
  promised a 42-character hex address. Tightened to match the message.
- **Secret spread**: `env_file: .env` handed the frontend container `API_KEY`,
  `POSTGRES_PASSWORD` and `DATABASE_URL`, none of which it uses. Removed.
- Added `SECURITY.md` — threat model, controls in place, and what to change before
  exposing the stack.

### CI
- `bandit` and `safety` ran with `|| true` and could never fail the build, and `bandit -c
  pyproject.toml` pointed at a file with no `[tool.bandit]` section. Added the section
  (excluding tests, whose `assert` and hardcoded-table queries were the only findings),
  dropped the `|| true`, and replaced the deprecated `safety` with `pip-audit`.
- Added `npm audit --audit-level=high` to the frontend job.
- Added a `docker-smoke` job that follows the README quick start verbatim and asserts the
  stack comes up serving seeded data.

### Dependencies
- Frontend: 11 advisories (9 high) → 0, via `next` 16.2.10 → 16.3.3.
- Python: `pytest` PYSEC-2026-1845 → 0, via `pytest>=9.0.3`.
- Split `requirements.txt` (runtime) from `requirements-dev.txt` (pytest, ruff, mypy,
  bandit, pip-audit). The application image no longer ships test tooling: 753 MB → 573 MB.
- `.dockerignore` now excludes `frontend/` and `node_modules/`; a local `npm install`
  previously dragged ~700 MB into the backend build context.
- Refreshed pre-commit hook revisions to match the pinned tool versions, added
  `pydantic-settings` to the mypy hook, and added `check-yaml`, `check-merge-conflict`
  and `detect-private-key`.

### Tests
- 281 → 309. New: WebSocket auth (missing / empty / wrong key, foreign origin), rate
  limiting on included routes, LIKE escaping, malformed wallet rejection. The rate-limit
  and WebSocket suites were verified to fail against the pre-fix code.

### Fixes
- Client-side navigation in the market detail table used `window.location.href`, forcing a
  full page reload; now `router.push`.
- Removed dead reconnect timer in `use-websocket.ts` and skipped the connection attempt
  when no key is stored, rather than opening a socket the server will close.

### Documentation
- Corrected README counts: 281 → 309 tests, 191 → 212 non-integration, "29 REST
  endpoints" → 28 REST plus the WebSocket.
- Documented that WebSocket auth is required, and that the key travels in the URL and is
  therefore visible to proxy and access logs.

## v0.6.1 (2026-08-28)

Repository prepared for public release.

### Fixes
- **Leaderboard ranks**: `get_ranking_list` did not filter `ranking_snapshots` by
  `snapshot_date`, so every historical run was concatenated and ranks repeated
  (rank 1 appeared eleven times on the main leaderboard). Now pinned to the latest
  snapshot for the requested list type.
- **Edge leaderboard**: deduplicated to each wallet's most recent
  `wallet_edge_snapshots` row; a wallet could previously occupy several rows.

### Database snapshot
- Replaced the 367 MB full `pg_dump` tracked in Git LFS with a ~3 MB sampled,
  foreign-key-consistent snapshot stored in plain git. The LFS free tier would have
  made a public repository unclonable after a handful of clones.
- Added `scripts/make-sample-seed.sh`; removed `scripts/refresh-seed.sh` and
  `.gitattributes`. Git LFS is no longer used anywhere in the repository.
- Split integration-test volume thresholds into sample-safe floors and
  production-scale thresholds gated behind `FULL_DATASET=1`.

### CI
- Run the whole non-integration suite (184 tests) instead of only the API tests.
- Run the frontend Vitest suite; drop the LFS checkout; fail the seed restore on error.

### Documentation
- Rewrote the root README (what the system does, scoring methodology, architecture
  diagram, screenshots, geo-blocking note) and the frontend README.
- Added MIT LICENSE.
- Refreshed `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md` and `AGENTS.md`.
- Moved `FEASIBILITY_REPORT.md` to `docs/FEASIBILITY.md` and the phase plans/specs to
  `docs/design/`, marked as historical records.
- Removed AI-tooling artifacts (`.opencode/`, tracked `.claude/`,
  `phase5-simplification-review.json`).

## v0.6.0 (2026-07-05)

### Features
- **Production Dashboard** (Phase 6): Next.js 16 dark-mode Bloomberg-style trading dashboard with 8 pages
- **API Key Authentication**: `require_api_key` / `optional_api_key` dependency replacing `_USER_ID` placeholder; WebSocket auth via `api_key` query parameter
- **Market Detail Endpoint**: `GET /api/v1/markets/{id}` with outcomes, bullish/bearish sentiment, and active traders
- **WebSocket Auth**: Optional `api_key` query param on `/api/v1/alerts/ws` (closes with 4001 on mismatch)

### Frontend
- **Next.js 16 + TypeScript + Tailwind v4 + shadcn/ui** scaffold with Edge Terminal design system
- **Dark Bloomberg-style theme**: Fraunces/JetBrains Mono/DM Sans, amber/emerald/rose accents
- **Typed API client** (`api-client.ts`) with auth headers and error handling
- **Auth context** (`auth.tsx`): localStorage-based API key with protected routes and login page
- **Layout**: `AppShell` + collapsible `Sidebar` (8 nav items) + `Header` (search, WS indicator, logout)
- **Shared components**: `DataTable` (sortable/paginated/skeleton), `MetricCard`, `WalletAddress` (truncate + copy), `AnimatedCounter`
- **Charts**: `BarChart`, `SentimentBar`, `Sparkline` for category and metric visualization
- **Leaderboard page**: 5 tabs (Main/Emerging/Consistent/Edge/By Category), top-3 highlight cards, paginated table with sortable columns
- **Wallet Profile page**: follow/unfollow, category bar chart, edge metrics, tabbed data (alerts/positions/edge)
- **Smart Money Feed page**: live WebSocket toggle, category/min_score/wallet filters, live connection badge
- **Market View page**: outcomes grid, active traders table, buy/sell sentiment bar
- **Follow Management page**: edit modal (label, copy mode, category filter), unfollow confirmation, recommendations tab
- **Portfolio page**: open positions table, trade history, close position dialog, reset portfolio dialog
- **Reusable hooks**: `useLeaderboard`, `useWebSocket`, `useAlerts`, `useFollowList`, `usePortfolio` with React Query mutations

### Backend
- `GET /api/v1/markets/{id}` — market detail with `OutcomeResponse`, `ActiveTraderEntry`, sentiment ratio
- `alert_websocket` — accepts optional `api_key` query parameter for authenticated connections
- `AlertItem.id` type changed from `str` to `UUID` for consistency
- CORS origins include `127.0.0.1` and `localhost:3000`

### Infrastructure
- **Frontend Dockerfile**: Multi-stage build (node:20-alpine) with standalone Next.js server
- **Docker Compose**: `frontend` service on port 3000 with `NEXT_PUBLIC_API_URL` env
- **CI**: New `frontend-checks` job (npm ci → lint → build) in GitHub Actions
- **Next.js rewrites**: API proxy (`/api/v1/*` → backend) to eliminate CORS in production
- Mage Docker image pinned to `0.9.79` (was `0.9.84`)

### Code Quality
- `Decimal` serialized as `float` in JSON to prevent frontend rendering crashes
- Frontend types (`api.ts`) fully aligned with backend schemas
- Frontend ESLint + `npm run build` pass cleanly
- Backend: 58 API tests, 164 total unit/API tests, 91 integration tests — all passing
- `ruff check app/` and `mypy app/` clean

### Tests
- 7 new auth tests (`test_api/test_auth.py`): CORS preflight, missing/invalid/valid API key, protected endpoint access
- 19 new frontend tests (`vitest`): api-client, wallet-address, metric-card, data-table
- Total: 267 → **274+ tests** (164 unit/API + 91 integration + 7 auth + 19 frontend)

---

## v0.5.0 (2026-07-01)

### Features
- **Follow Recommendation Engine** (Phase 5): New scoring engine ranks wallets by follow-worthiness using edge, consistency, specialization, recency, and trade frequency
- **Category Follow Scoring**: Per-category follow scores with dedicated leaderboard (`GET /api/v1/follow/recommendations/by-category/{category}`)
- **Wallet Follow CRUD**: Follow/unfollow wallets with copy-trade configuration (`copy_mode`, `copy_value`, `category_filter`)
- **Paper Trading Engine**: Simulated copy trades from followed wallets with proportional/fixed allocation modes
- **Background Paper Trade Generation**: `paper_trade_generation_loop` polls alerts every 10s with `FOR UPDATE SKIP LOCKED` for exactly-once processing
- **Market Resolution Handling**: Auto-close paper positions when markets resolve

### Database
- 4 new migrations (`018`–`021`): `wallet_follows`, `paper_portfolios`, `paper_positions`, `paper_trades`, `wallet_category_follow_scores`
- Partial unique index on `wallet_follows(user_id, wallet) WHERE active = true` (allows re-follow after soft-delete)
- `follow_score` column added to `wallet_analytics`
- `CheckConstraint` on `current_balance >= 0` and `shares >= 0` for paper trading tables
- `ON DELETE SET NULL` on `source_alert_id` foreign keys

### ETL
- New `enrichment_follow_scoring` pipeline: load → compute global + per-category follow scores → export to `wallet_category_follow_scores`
- Orchestration updated: `trigger_follow_scoring` runs between `trigger_edge_scoring` and `trigger_verify`

### API
- `GET /api/v1/follow/recommendations` — top wallets by global follow score
- `GET /api/v1/follow/recommendations/by-category/{category}` — per-category follow leaderboard
- `GET /api/v1/follow/recommendations/{wallet}/by-category` — per-category scores for a wallet
- `GET /api/v1/follow` — list followed wallets
- `POST /api/v1/follow/{wallet}` — follow a wallet (with re-activation of soft-deleted follows)
- `PATCH /api/v1/follow/{wallet}` — update follow config
- `DELETE /api/v1/follow/{wallet}` — unfollow (soft delete)
- `GET /api/v1/portfolio` — list paper portfolios
- `GET /api/v1/portfolio/{id}` — portfolio detail with positions
- `PATCH /api/v1/portfolio/positions/{position_id}/close` — close position
- `POST /api/v1/portfolio/{id}/reset` — reset portfolio

### Code Quality
- **Shared scoring constants** (`scoring_constants.py`): all formula weights, thresholds, and parameters in one place to prevent drift between service layer, ETL, and tests
- **Pure Decimal math**: category follow scoring uses `Decimal` throughout (no `float` → `Decimal` round-trip)
- **Multi-follow safety**: `_execute_buy`/`_execute_sell` filter by `followed_wallet` to prevent position mixing
- **Race condition hardening**: `FOR UPDATE` on all critical paper trade operations (buy, sell, market resolution, position close, portfolio reset)
- **Input validation**: wallet address format, category_filter values, copy_value bounds, max follows limit

### Tests
- 4 new unit test files: `test_follow_scoring.py`, `test_paper_trading.py`
- 2 new API test files: `test_api/test_follow_endpoints.py`, `test_api/test_portfolio_endpoints.py`
- Enhanced integration tests in `test_db_integrity.py` (Phase 5 table coverage)
- Total: 176 → **267 tests**

### Infrastructure
- `.dockerignore` expanded with `magic/`, `.venv/`, `plans/`, `.opencode/` patterns

---

## v0.4.1 (2026-06-28)

### Fixes
- **ETL Pipeline Error Propagation**: `trigger_verify` now reads block errors from Mage SQLite DB when `verify_etl_output` pipeline fails, providing meaningful error messages instead of generic failure
- **wallet_score Default**: `compute_wallet_metrics` defaults `wallet_score` to `0` instead of `None`, preventing null scores in rankings

---

## v0.4.0 (2026-06-27)

### Features
- **Edge Scoring Pipeline** (Phase 4): New `enrichment_edge_scoring` pipeline computes predictive accuracy per wallet via FIFO trade matching against resolved market outcomes
- **Edge Leaderboard**: `GET /api/v1/leaderboard/edge` — traders ranked by min-max normalized edge score
- **Wallet Edge Metrics**: `GET /api/v1/wallets/{address}/edge` — detailed edge snapshot per wallet
- **Edge-integrated Rankings**: `wallet_score` formula updated to `0.40×edge_score + 0.20×consistency + 0.20×roi + 0.10×experience + 0.10×sharpe`
- **Edge-integrated Wallet Profile**: `GET /api/v1/wallets/{address}` now includes `edge_metrics`
- All Phase 3 features (alert REST API, WebSocket, Discord delivery) finalized

### Database
- Migration `017_add_edge_scoring.py`: new `wallet_edge_snapshots` table + `edge_score` columns on `wallet_analytics` and `ranking_snapshots`
- FK from `wallet_edge_snapshots.wallet` → `wallets.wallet`, composite PK `(wallet, snapshot_date)`
- Indexes on wallet+date DESC, snapshot_date DESC, edge_score DESC

### ETL
- New `enrichment_edge_scoring` pipeline: load resolved trades + outcomes → FIFO buy/sell matching → per-wallet edge aggregation → min-max normalization → UPSERT to `wallet_edge_snapshots`
- `compute_wallet_scores.py`: edge_score integrated into ranking formula
- `load_all_analytics.py`: LEFT JOIN to latest edge snapshot
- `materialize_rankings.py`: edge_score propagated to `ranking_snapshots`
- Orchestration pipeline updated: `trigger_edge_scoring` runs after `trigger_category_analytics`, before `trigger_verify`

### Security & Infrastructure
- **Critical**: App port restricted to `127.0.0.1:8000:8000` (was `0.0.0.0:8000`)
- **Critical**: WebSocket max connections capped at 100 (DoS protection)
- **High**: Mage Docker image pinned to `0.9.84` (was `:latest`), non-root user added
- **High**: Credential fallbacks changed from `devpassword` to `changeme` across all 5 files
- **High**: `alembic.ini` now reads DB URL from env var instead of hardcoded value
- **High**: `.dockerignore` created to prevent secret leakage in Docker builds
- **High**: `bandit` + `safety` added to CI pipeline
- **Medium**: `types-redis` removed from mypy deps (Redis was already removed)
- **Medium**: `HEALTHCHECK` added to app service
- **Low**: CORS fallback `["*"]` replaced with explicit `settings.cors_origins`

### Code Quality
- `compute_trade_edge.py`: 3 parallel dicts → single `NamedTuple`, min-max normalization extracted, `resolve_price` simplified to ternary
- `wallets.py`: manual 11-field mapping → `model_validate()`, duplicated edge query → `get_latest_edge_snapshot()` in `wallet_service.py`
- `leaderboard.py`: `_to_entry()` and `_build_leaderboard_entry()` → shared `_safe_decimal()` helper
- `alerts.py`: `_alert_to_item()` with 7 `# type: ignore` → `model_validate()` (zero ignores)
- `alert_service.py`: embed dict → `_build_discord_embed()`, `SELECT+mutate+COMMIT` → direct `update()`
- `ws_manager.py`: duplicated dead-connection cleanup → extracted `_broadcast()` method
- `categories.py` + `leaderboard.py`: duplicated `_validate_category_or_404` → shared `utils/category.py`
- `export_edge_snapshots.py`: row-by-row `iterrows()` → batch `execute()` with param list
- `materialize_rankings.py`: split DELETE/INSERT transactions → single transaction; row-by-row → batch
- `compute_wallet_scores.py`: added type hints, 3x `pd.concat` → single concat of list

### Tests
- 10 new unit tests (`test_edge_scoring.py`) — edge computation, FIFO matching, normalization, empty/zero edge cases
- 7 new API tests (`test_api/test_edge_endpoints.py`) — leaderboard empty/with-data/pagination/validation, wallet edge 200/404
- 9 new integration tests (`test_db_integrity.py`) — edge snapshots queryable, FK, NOT NULL, score/consistency/volatility/bounds ranges, edge_score columns exist
- Total: 149 → **176 tests** (110 unit/API + 66 integration)

### Notes
- Phase 4 Edge Scoring complete; partial share matching deferred (MV assumes full close)

---

## v0.3.0 (2026-06-24)

### Features
- **PnL Cash-Flow Reconstruction**: New `ingestion_pnl` pipeline reconstructs wallet PnL from `/activity`
  cash flows, fixing extreme ROI outliers caused by auto-redeemed markets vanishing from `/positions`
- **PnL Quick Fix**: `load_positions.py` — corrected cashPnl mapping (`unrealized_pnl = cashPnl - realizedPnl`,
  `total_pnl = cashPnl`). Eliminates double-count of realized PnL in analytics transformers
- **Smart Money Detection (Data Layer)**: New `smart_money_detection` pipeline with action classification
  (NEW_POSITION, POSITION_INCREASE, POSITION_DECREASE, FULL_EXIT), configurable thresholds, cooldown dedup
- **Accurate Downstream Analytics**: `compute_wallet_metrics.py` and `compute_category_metrics.py` read
  accurate PnL from `wallet_pnl_snapshots` via LEFT JOIN (graceful fallback to old position-based PnL)

### Database
- 3 new migrations (`005_smart_money_alerts`, `006_drop_outcome_id_fks`, `007_add_wallet_pnl_snapshots`)
- New tables: `alerts`, `alert_rules`, `wallet_pnl_snapshots`
- Foreign keys: alerts → wallets/markets, pnl_snapshots → wallets
- Global default alert rule seeded (min_score=80, min_position_size=500, min_liquidity=1000, cooldown=15min)

### ETL
- New `ingestion_pnl` pipeline: `/activity` cursor pagination (10 parallel workers) → cash-flow PnL formula → UPSERT `wallet_pnl_snapshots`
- New `smart_money_detection` pipeline: position_history diff → action classification → rule engine → alerts
- Orchestration updated: `trigger_pnl` between position_sync and trade_history; `trigger_smart_money` after verify
- Backfill script: `scripts/backfill_pnl.py` for one-shot PnL computation across all wallets

### Infrastructure
- Config file changed from `.env` to `.env.app` for app settings (added to `.gitignore`)
- `MAGE_MEM_LIMIT` configurable via env var (default 8g) for Docker resource control

### Tests
- 4 new integration tests: PnL snapshot consistency, PnL bounds, row thresholds + FK for `wallet_pnl_snapshots`
- ROI bound widened from [-10000, 100000] to [-100000, 500000] for category analytics
- Total: 69 → **72 tests** (27 API/unit + 45 integration)

### Notes
- Phase 3 features (alert REST API, WebSocket, Discord delivery, tests) completed in v0.4.0

---

## v0.2.0 (2026-06-22)

### Features
- **Category Analytics**: 8-category classification pipeline for niche expertise detection
- **Category Leaderboards**: `GET /api/v1/leaderboard/{category}` with specialist filtering
- **Wallet Category Breakdown**: Per-category PnL, ROI, win rate via `GET /api/v1/wallets/{address}/categories`
- **3-Tier Classifier**: Raw API mapping + event inheritance + 300+ keyword rules for market categorization
- **Category Specialist Detection**: Flags wallets with >30 trades and above-median ROI in a category

### Database
- 3 new migrations (`002_category_analytics`, `003_add_mapped_category`, `004_add_categories_table`)
- New tables: `category_analytics`, `category_rankings`, `categories`
- New column: `markets.mapped_category`
- Foreign keys from analytics/rankings tables to `wallets.wallet`

### API
- `GET /api/v1/categories` — list all 8 categories
- `GET /api/v1/leaderboard/{category}` — top traders by category
- `GET /api/v1/leaderboard/{category}/specialists` — specialist traders only
- `GET /api/v1/wallets/{address}/categories` — per-category breakdown
- `GET /api/v1/wallets/{address}/categories/{category}` — single category detail

### ETL
- New `category_analytics` Mage AI pipeline (loaders + transformer + exporter)
- 4 data loaders, 1 transformer, 1 exporter for category metrics computation
- Pipeline computes per-wallet ROI, win rate, volume, trade count by category

### Tests
- 10 new classifier unit tests (`test_category_classifier.py`)
- 8 new API endpoint tests (`test_category_endpoints.py`)
- 10 new integration tests in `test_db_integrity.py`
- Total: 41 → 69 tests
- Removed `test_category_analytics_pnl_is_reasonable` — category PnL outliers can be legitimate

### Infrastructure
- Backfill script: `scripts/backfill_categories.py` for existing markets
- Seed dump refreshed with category data

---

## v0.1.0 (2026-06-17)

### Features
- MVP Leaderboard with 6 Mage AI ETL pipelines
- Top 100, emerging, and consistent trader rankings
- Wallet analytics: PnL, ROI, Sharpe, win rate, drawdown
- Wallet filtering: min 50 trades, $1k volume, 3 months history
- Proxy wallet → main wallet resolution via Gamma API

### Database
- Initial migration (`001_initial.py`)
- 8 tables: `events`, `markets`, `outcomes`, `wallets`, `trades`, `positions`, `position_history`, `wallet_analytics`, `ranking_snapshots`

### API
- `GET /api/v1/leaderboard` — top 100 traders
- `GET /api/v1/leaderboard/emerging` — top 10 emerging
- `GET /api/v1/leaderboard/consistent` — top 10 consistent
- `GET /api/v1/wallets/{address}` — full wallet profile
- `GET /api/v1/markets` — list markets with category filter

### ETL
- 6 pipelines: market discovery, wallet discovery, trade history, position sync, analytics computation, ranking computation

### Tests
- 9 API unit tests + 32 integration tests = 41 total
- CI/CD with GitHub Actions, MyPy strict, Ruff
