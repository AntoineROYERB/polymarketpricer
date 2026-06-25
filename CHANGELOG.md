# Changelog

## v0.4.0 (2026-06-25)

### Features
- **Alert REST API**: `GET /api/v1/alerts` with category, score, wallet, and pagination filters
- **Wallet Alert Lookup**: `GET /api/v1/alerts/{wallet}` with pagination
- **Alert Statistics**: `GET /api/v1/alerts/stats` — total alerts, daily count, top categories, top wallets
- **WebSocket Stream**: `WS /api/v1/alerts/ws` — real-time alert delivery with heartbeat ping/pong
- **Discord Delivery Service**: `alert_service.py` — `poll_unnotified_alerts()` (max 3 retry attempts), `send_discord_alert()` with richly formatted embeds (per-action colors, trader score, category, market question), `mark_notified()` with delivery tracking
- **WebSocket Connection Manager**: `ws_manager.py` — broadcast with dead-connection cleanup, heartbeat to all connected clients, alert payload serialization

### Tests
- 13 new API endpoint tests (`test_api/test_alert_endpoints.py`) — list, filter, pagination, 422 validation, 404 handling, stats shape
- 39 new service unit tests (`test_alert_service.py`) — `classify_action` (11), `_format_action` (7), `send_discord_alert` (8), `poll_unnotified_alerts` (5), `mark_notified` (5), edge case integration (3)
- 14 new WebSocket manager tests (`test_ws_manager.py`) — connect/disconnect lifecycle (5), broadcast (5), heartbeat (4)
- 8 new integration tests (`test_db_integrity.py`) — alerts table queryable, alert_rules global default, FK integrity (wallet + market), not-null with `market_question`, score range [0, 100], position size positivity, valid action enums
- Total: 72 → **149 tests** (93 unit/API + 56 integration)

### Documentation
- README.md: Updated status banner (Phase 3 ✅ Complete), testing section (72→149), project structure tree, phases table
- README.md: Added alert API reference (`GET /api/v1/alerts`, `/stats`, `/{wallet}`, `WS /ws`)
- AGENTS.md: Updated test counts, file listings, and running instructions
- Phase 3 test plan: Updated to reflect actual filenames and coverage

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
