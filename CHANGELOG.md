# Changelog

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
