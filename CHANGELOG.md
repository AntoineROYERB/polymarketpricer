# Changelog

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
- Total: 41 → 70 tests (+ category-specific integration coverage in test suite)

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
