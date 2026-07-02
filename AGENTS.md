# polymarketpricer

Multi-pipeline ETL system: Polymarket data → PostgreSQL → FastAPI backend.
Phase 5 (Follow Recommendation Engine, Paper Trading) is in progress.

## Essential commands

```bash
# Start services
docker compose up -d

# Run migrations (must use `exec`)
docker compose exec app alembic upgrade head

# Run a single ETL pipeline (non-obvious path)
docker compose exec mage mage run /home/src/default_repo ingestion_market_discovery

# Run all pipelines sequentially
./scripts/run-all-pipelines.sh

# Pipe seed into postgres container
docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql.gz

# Test suites
python -m pytest app/tests/test_api/ -v              # mock-based, no DB needed
python -m pytest app/tests/test_db_integrity.py -m integration -v  # needs postgres running
python -m pytest app/tests/ -v                        # all tests

# Pre-commit checks (also run by ruff pre-commit hook)
ruff check app/
mypy app/
```

## Architecture

**Three Docker services**: `postgres` (16-alpine, port 5432), `mage` (ETL, port 6789), `app` (FastAPI, port 8000).

**11 sequential ETL pipelines** under `magic/default_repo/pipelines/`:

`market_discovery → wallet_discovery → position_sync → pnl → trade_history → analytics_computation → ranking_computation → category_analytics → edge_scoring → smart_money_detection → verify_etl_output`

The `verify_etl_output` pipeline is a dry-run integrity check — it does not modify data.

Orchestration pipeline runs all 11 in order. New pipelines must be added to the orchestration pipeline too.

**FastAPI routes** live in `app/api/v1/` and are aggregated in `app/api/router.py`. Rate limit: 60 req/min default (slowapi). CORS allows `GET` only.

**Background loops** in `app/main.py`:
- Alert delivery: polls `ALERT_POLL_INTERVAL_SECONDS` (default 10s), broadcasts via WebSocket + optional Discord
- Paper trade generation: polls every 10s, uses `FOR UPDATE SKIP LOCKED` for exactly-once processing
- WebSocket heartbeat: every 30s (at `/api/v1/alerts/ws`)

**Category classifier** lives in `magic/default_repo/utils/category_classifier.py` (not in `app/`). Three-tier fallback: raw API map → event inheritance → keyword rules. 8 target categories.

**21 Alembic migrations** under `alembic/versions/`. Always run `alembic upgrade head` after restoring seed or pulling new migrations.

## Testing guide

Three tiers with different prerequisites:

| Suite | Command | Needs DB? | Notes |
|-------|---------|-----------|-------|
| API mock tests | `python -m pytest app/tests/test_api/ -v` | No | Uses ASGITransport with mocked session |
| Service unit tests | `python -m pytest app/tests/test_alert_service.py app/tests/test_ws_manager.py app/tests/test_edge_scoring.py -v` | No | Pure function + mocked service tests |
| Integration tests | `python -m pytest app/tests/test_db_integrity.py -m integration -v` | Yes (postgres running) | Uses sync psycopg2 connection; derives sync URL from async `DATABASE_URL` by replacing driver prefix |

**Key config in pyproject.toml**: `asyncio_mode = "auto"`, `testpaths = ["app/tests"]`, integration marker defined. Ruff line-length 100. mypy strict with SQLAlchemy plugin.

## Code quality

Pre-commit hooks (`.pre-commit-config.yaml`): ruff (lint + fix), ruff-format, mypy (strict), trailing-whitespace, end-of-file-fixer.

Run these before committing: `ruff check app/ && mypy app/ && python -m pytest app/tests/test_api/ -v`

CI workflow (`.github/workflows/ci.yml`) runs three jobs: `lint` (ruff, mypy, bandit, safety), `api-tests`, `integration-tests` (restores seed, runs migrations, then tests).

## Environment gotchas

- **`DATABASE_URL` differs inside vs outside Docker**: docker-compose.yml hardcodes `postgresql+asyncpg://app:devpassword@postgres:5432/polymarket` (hostname `postgres`). The `.env` value uses `localhost` for local dev.
- **Git LFS**: `docker/initdb/seed.sql.gz` is tracked via LFS. Run `git lfs pull` after clone.
- **Seed restore order**: seed data → then `alembic upgrade head` (never the reverse).
- **Integration tests use sync psycopg2**: derive sync URL by replacing `postgresql+asyncpg://` → `postgresql+psycopg2://`.

## Reference docs

Detailed documentation lives alongside code:

| File | Covers |
|------|--------|
| `docs/ARCHITECTURE.md` | System diagram, data flow |
| `docs/API.md` | All REST + WebSocket endpoints |
| `docs/ALERTS.md` | Alert pipeline, Discord setup |
| `docs/DATABASE.md` | Schema, category classification, migrations |
| `docs/DEVELOPMENT.md` | Local setup, testing, code quality |
| `.opencode/opencode.jsonc` | OpenCode agent configurations |
| `.opencode/agents/qa-engineer.md` | QA review agent instructions |
| `.opencode/commands/commit.md` | Commit command (runs pre-commit checks) |
| `.opencode/plans/` | Phase specifications for coding agents |
