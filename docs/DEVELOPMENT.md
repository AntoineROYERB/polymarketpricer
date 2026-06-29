# Development

## Prerequisites

- Python 3.12+
- Docker & Docker Compose

## Local Setup

```bash
# Copy environment template and configure credentials
cp .env.sample .env
# Then edit .env with your actual values (database URL, Discord webhook, etc.)

# Start infrastructure (PostgreSQL + Redis)
docker compose up -d postgres redis

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start the app
uvicorn app.main:app --reload
```

## Testing

The project has four test suites:

```bash
# Unit / API tests (mocked, no Docker needed)
python -m pytest app/tests/test_api/ -v

# Service / classifier unit tests (mocked, no Docker needed)
python -m pytest app/tests/test_alert_service.py app/tests/test_ws_manager.py app/tests/test_edge_scoring.py -v

# Edge scoring unit tests
python -m pytest app/tests/test_edge_scoring.py -v

# Integration tests (requires docker compose up -d)
python -m pytest app/tests/test_db_integrity.py -m integration -v

# Run all tests
python -m pytest app/tests/ -v

# With coverage
python -m pytest app/tests/ --cov=app -v
```

The **175 tests** (111 unit/API + 64 integration) validate row counts, referential integrity,
not-null constraints, data quality ranges, timestamp sanity, cross-table consistency,
data filtering, alert classification logic, Discord delivery, WebSocket streaming,
and edge scoring (FIFO matching, normalization, edge quality ranges) —
with all CI checks enforced via GitHub Actions (`mypy --strict` + `ruff`).

### Unit / API Tests (47 tests)

Mock-based tests that verify endpoint behaviour without a real database:

| File | Tests | What it validates |
|---|---|---|
| `test_endpoints.py` | 9 | Phase 1 endpoints (leaderboard, wallets, markets) |
| `test_category_endpoints.py` | 8 | Phase 2 endpoints (category leaderboards, wallet categories) |
| `test_alert_endpoints.py` | 13 | Phase 3 alert endpoints (list, filter, pagination, stats, 404/422 error handling) |
| `test_edge_endpoints.py` | 7 | Phase 4 edge endpoints (leaderboard empty/with-data/pagination, wallet edge 200/404) |
| `test_category_classifier.py` | 10 | Category classification for all 8 categories + unclassifiable + case insensitivity (at `app/tests/`) |

### Service / Unit Tests (63 tests)

Pure function and mocked-service tests:

| File | Tests | What it validates |
|---|---|---|
| `test_alert_service.py` | 39 | `classify_action`, `_format_action`, `send_discord_alert`, `poll_unnotified_alerts`, `mark_notified`, edge cases |
| `test_ws_manager.py` | 14 | Connection lifecycle, broadcast, heartbeat, dead connection cleanup |
| `test_edge_scoring.py` | 10 | Edge computation (FIFO matching, normalization, empty/zero edge cases) |

### Integration Tests (64 tests)

Connect to the actual PostgreSQL instance and validate ETL pipeline output:

| Category | Tests | What it validates |
|---|---|---|
| Row counts | 12 | Each populated table meets a minimum row threshold |
| Referential integrity | 9 | No orphaned foreign keys across all FK relationships (incl. `wallet_pnl_snapshots`) |
| Not-null constraints | 8 | Critical columns (`question`, `price`, `timestamp`, `wallet`, analytics metrics, category analytics, pnl_snapshot keys) have no NULLs |
| Analytics quality | 7 | PNL within ±500k, win_rate in [0,1], wallet_score in [0,100], drawdown ≤ 0, profit_factor ≥ 0, category ROI/win_rate in range |
| PnL snapshot quality | 2 | `total_pnl = realized + unrealized`, PnL ≤ 100× cost basis |
| Timestamp sanity | 2 | No future timestamps in `trades` or future dates in `wallet_analytics` |
| Cross-table consistency | 5 | Analytics/trade wallets exist in `wallets`, markets have at least one outcome, category wallets exist in `wallets`, pnl_snapshot FK valid |
| ROI range (relaxed) | 1 | Category analytics ROI within [-100000, 500000] |
| Alerts (Phase 3) | 8 | Alerts table queryable, alert_rules global default, FK (wallet, market), NOT NULL (8 cols), score range [0,100], position_size > 0, valid action enums |
| PnL snapshot | 3 | Consistency, bounds, plus 1 combined with row counts |
| Edge Scoring (Phase 4) | 9 | Edge snapshots queryable, FK, NOT NULL (4 cols), edge_score in [0,1], edge_consistency in [0,1], edge_volatility ≥ 0, avg_edge bounds, edge_score column in wallet_analytics, edge_score column in ranking_snapshots |

## Code Quality

```bash
# Lint
ruff check app/

# Type check
mypy app/ --strict

# Pre-commit (install once)
pre-commit install
pre-commit run --all-files
```

## Environment Configuration

The project uses a two-file `.env` system:

| File | Tracked by git | Purpose |
|------|---------------|---------|
| `.env.sample` | **Yes** | Template with placeholder values and explanatory comments. Copy this to `.env`. |
| `.env` | **No** (`.gitignore`) | Actual secrets and config. Per-developer, never committed. |

```bash
# First time setup
cp .env.sample .env
# Then edit .env with your actual values
```

### Variables overview

| Variable | Required? | Default | Used by | Description |
|----------|-----------|---------|---------|-------------|
| `DATABASE_URL` | ✅ | — | `app/`, `mage/` | Asyncpg connection string |
| `POSTGRES_DB` | ✅ | `polymarket` | `postgres` service | Database name |
| `POSTGRES_USER` | ✅ | `app` | `postgres` service | Database user |
| `POSTGRES_PASSWORD` | ✅ | `devpassword` | `postgres` service | Database password |
| `DISCORD_WEBHOOK_URL` | ❌ | empty | `app/` | Discord webhook for smart money alerts |
| `ALERT_POLL_INTERVAL_SECONDS` | ❌ | `10` | `app/` | Background poll interval for new alerts |
| `MAGE_MEM_LIMIT` | ❌ | none | `mage` service | Docker memory limit |
| `TARGET_WALLET_COUNT` | ❌ | `1000` | `mage/` | Target wallets to discover |
| `FULL_SYNC` | ❌ | `false` | `mage/` | Force full sync (bypass incremental) |
| `VERIFY_MIN_*` | ❌ | see `.env.sample` | `mage/` | Row count thresholds for ETL verification |
