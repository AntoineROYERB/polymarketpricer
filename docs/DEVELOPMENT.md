# Development

## Prerequisites

- Python 3.12+
- Docker & Docker Compose

## Local Setup

```bash
# Copy environment template and configure credentials
cp .env.sample .env
# Then edit .env with your actual values (database URL, Discord webhook, etc.)

# Start infrastructure (PostgreSQL). On its very first boot the container loads
# docker/initdb/seed.sql.gz — a 3 MB sampled snapshot of the production database —
# so you get a populated instance without touching the Polymarket APIs.
docker compose up -d postgres

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

```bash
# Unit / API tests — mocked, no database needed (184 tests)
python -m pytest app/tests -m "not integration"

# Integration tests — require a running, seeded database (97 tests)
python -m pytest app/tests -m integration

# Everything
python -m pytest app/tests

# With coverage
python -m pytest app/tests --cov=app

# Frontend component tests (19 tests)
cd frontend && npm test
```

### Unit / API tests (184)

Mock-based; they never touch PostgreSQL.

| File | What it validates |
|---|---|
| `test_api/test_endpoints.py` | Leaderboard, wallets, markets, health |
| `test_api/test_category_endpoints.py` | Category leaderboards and wallet category breakdowns |
| `test_api/test_alert_endpoints.py` | Alert list, filters, pagination, stats, error handling |
| `test_api/test_edge_endpoints.py` | Edge leaderboard and per-wallet edge |
| `test_api/test_follow_endpoints.py` | Follow list, recommendations, follow/unfollow |
| `test_api/test_portfolio_endpoints.py` | Paper portfolio, positions, trades, close, reset |
| `test_api/test_auth.py` | Bearer-token guard on write endpoints |
| `test_alert_service.py` | `classify_action`, Discord embed and delivery, poll/mark-notified |
| `test_ws_manager.py` | Connection lifecycle, broadcast, heartbeat, dead-connection cleanup |
| `test_edge_scoring.py` | FIFO round-trip matching, normalization, degenerate cases |
| `test_follow_scoring.py` | Follow-score formula, recency decay, frequency sigmoid, thresholds |
| `test_paper_trading.py` | Copy-trade sizing, fills, PnL, market resolution |
| `test_category_classifier.py` | Keyword classification across all categories |

### Integration tests (97)

`test_db_integrity.py` and `test_db_integrity_advanced.py` connect to a real database and
assert on ETL output: row-count floors, referential integrity across every FK, not-null
constraints on critical columns, value ranges (win rate, ROI, edge score, drawdown,
profit factor), timestamp sanity, and cross-table consistency.

Volume thresholds come in two tiers. The default floors hold against the committed
sampled seed, so the suite runs in CI. Production-scale thresholds (50k markets, 50k
trades, ...) are gated behind an environment flag and only make sense after a full ETL
run:

```bash
FULL_DATASET=1 python -m pytest app/tests -m integration
```

### Refreshing the seed

After a full ETL run, regenerate the committed snapshot:

```bash
./scripts/make-sample-seed.sh    # writes docker/initdb/seed.sql.gz (~3 MB)
```

The script samples the 200 highest-scoring wallets, their 120 most recent trades each,
and every event / market / outcome those trades reference, so the result stays
foreign-key consistent. It blanks `alert_rules.discord_webhook_url` — the seed is
committed to a public repository. Keep the file small: it lives in plain git, not Git
LFS.

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
| `API_KEY` | ✅ | — | `app/`, frontend | Bearer token guarding `/follow` and `/portfolio`. The app refuses to start without it — generate with `openssl rand -hex 32` |
| `CORS_ORIGINS` | ❌ | `["http://localhost:3000"]` | `app/` | JSON list of allowed browser origins; empty blocks all cross-origin requests |
| `DISCORD_WEBHOOK_URL` | ❌ | empty | `app/` | Discord webhook for smart money alerts |
| `ALERT_POLL_INTERVAL_SECONDS` | ❌ | `10` | `app/` | Background poll interval for new alerts |
| `MAGE_MEM_LIMIT` | ❌ | none | `mage` service | Docker memory limit |
| `TARGET_WALLET_COUNT` | ❌ | `1000` | `mage/` | Target wallets to discover |
| `FULL_SYNC` | ❌ | `false` | `mage/` | Force full sync (bypass incremental) |
| `VERIFY_MIN_*` | ❌ | see `.env.sample` | `mage/` | Row count thresholds for ETL verification |
