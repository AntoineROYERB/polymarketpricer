# polymarketpricer

Multi-pipeline ETL: Polymarket data → PostgreSQL → FastAPI → Next.js dashboard.

## Essential commands

```bash
docker compose up -d
docker compose exec app alembic upgrade head
docker compose exec mage mage run /home/src/default_repo orchestration  # all pipelines
docker compose exec mage mage run /home/src/default_repo ingestion_market_discovery  # single
./scripts/run-all-pipelines.sh [pipeline_name]      # orchestration by default, single if arg given
docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql.gz

# Tests (no DB needed)
python -m pytest app/tests/test_api/ -v
python -m pytest app/tests/test_follow_scoring.py app/tests/test_paper_trading.py -v
ruff check app/
mypy app/

# Integration (needs postgres running)
python -m pytest app/tests/test_db_integrity.py -m integration -v
```

## Architecture

**4 Docker services**: `postgres` (16-alpine, :5432), `mage` (ETL, :6789), `app` (FastAPI, :8000), `frontend` (Next.js 16, :3000).

**13 pipelines** (12 data + 1 orchestration) under `magic/default_repo/pipelines/`. Orchestrated in this sequential order:

`ingestion_market_discovery → ingestion_wallet_discovery → ingestion_position_sync → ingestion_pnl → ingestion_trade_history → enrichment_analytics_computation → category_analytics → enrichment_edge_scoring → enrichment_ranking_computation → enrichment_follow_scoring → verify_etl_output → smart_money_detection`

The orchestration pipeline (`orchestration/`) runs all 12 data pipelines plus a notify block. New pipelines must be added there too.

**API routes** in `app/api/v1/` aggregated in `app/api/router.py`. Rate limit: 60 req/min (slowapi). API key auth via `Authorization: Bearer <token>` header — two dependencies: `require_api_key` (401 on fail) and `optional_api_key` (returns `"user"` or `"default"`).

**Background loops** in `app/main.py`:
- Alert delivery: polls `ALERT_POLL_INTERVAL_SECONDS` (default 10s), broadcasts via WebSocket + optional Discord
- Paper trade generation: polls every 10s, `FOR UPDATE SKIP LOCKED` for exactly-once
- WebSocket heartbeat: every 30s at `/api/v1/alerts/ws`

**22 Alembic migrations** under `alembic/versions/`. Always run `alembic upgrade head` after restoring seed or pulling new migrations.

**Phase 5 implemented**: Follow recommendation engine (`app/services/follow_scoring.py`, scoring weights in `app/services/scoring_constants.py`), paper trading (`app/services/paper_trading.py`), follow/portfolio API endpoints, DB models `WalletFollow`, `PaperPortfolio`, `PaperPosition`, `PaperTrade`, `WalletCategoryFollowScore`.

**Frontend**: Next.js 16 app in `frontend/`. Uses API proxy rewrites (`next.config.ts`), Tailwind v4, shadcn/ui. Run standalone: `npm run dev` in `frontend/`.

## Testing guide

| Suite | Command | Needs DB? |
|-------|---------|-----------|
| API mock tests | `python -m pytest app/tests/test_api/ -v` | No |
| Service unit tests | `python -m pytest app/tests/test_follow_scoring.py app/tests/test_paper_trading.py app/tests/test_edge_scoring.py app/tests/test_alert_service.py app/tests/test_ws_manager.py -v` | No |
| Integration tests | `python -m pytest app/tests/test_db_integrity.py -m integration -v` | Yes |

API mock tests use ASGITransport with mocked session (`conftest.py`). Integration tests use sync psycopg2; sync URL derived by replacing `postgresql+asyncpg://` → `postgresql+psycopg2://`.

## Environment gotchas

- `DATABASE_URL` differs inside Docker (`postgres` hostname) vs `.env` (`localhost`). Docker compose hardcodes `postgresql+asyncpg://app:devpassword@postgres:5432/polymarket`.
- `docker/initdb/seed.sql.gz` tracked via Git LFS — run `git lfs pull` after clone.
- Seed restore order: seed data → `alembic upgrade head` (never reverse).

## Reference docs

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
| `frontend/AGENTS.md` | Next.js 16 breaking changes warning |
