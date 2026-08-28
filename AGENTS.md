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
python -m pytest app/tests -m "not integration"
ruff check app/
mypy app/

# Integration (needs a running, seeded postgres)
python -m pytest app/tests -m integration
FULL_DATASET=1 python -m pytest app/tests -m integration   # after a full ETL run
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

**21 Alembic migrations** under `alembic/versions/`. Always run `alembic upgrade head` after restoring seed or pulling new migrations.

**Phase 5 implemented**: Follow recommendation engine (`app/services/follow_scoring.py`, scoring weights in `app/services/scoring_constants.py`), paper trading (`app/services/paper_trading.py`), follow/portfolio API endpoints, DB models `WalletFollow`, `PaperPortfolio`, `PaperPosition`, `PaperTrade`, `WalletCategoryFollowScore`.

**Frontend**: Next.js 16 app in `frontend/`. Uses API proxy rewrites (`next.config.ts`), Tailwind v4, shadcn/ui. Run standalone: `npm run dev` in `frontend/`.

## Testing guide

| Suite | Command | Needs DB? |
|-------|---------|-----------|
| Unit + API (184) | `python -m pytest app/tests -m "not integration"` | No |
| Integration (97) | `python -m pytest app/tests -m integration` | Yes |
| Frontend (19) | `cd frontend && npm test` | No |

API mock tests use ASGITransport with mocked session (`conftest.py`). Integration tests use sync psycopg2; sync URL derived by replacing `postgresql+asyncpg://` → `postgresql+psycopg2://`.

## Environment gotchas

- `DATABASE_URL` differs inside Docker (`postgres` hostname) vs `.env` (`localhost`). Docker compose hardcodes `postgresql+asyncpg://app:devpassword@postgres:5432/polymarket`.
- `docker/initdb/seed.sql.gz` is a ~3 MB **sampled** snapshot in plain git (no Git LFS).
  Postgres loads it automatically on first boot via `/docker-entrypoint-initdb.d`.
  Regenerate with `./scripts/make-sample-seed.sh` after a full ETL run; keep it small.
- Seed restore order: seed data → `alembic upgrade head` (never reverse).
- Integration-test volume thresholds have two tiers: sample-safe floors by default,
  production volumes behind `FULL_DATASET=1`. Keep both in sync when the schema grows.

## Reference docs

| File | Covers |
|------|--------|
| `docs/ARCHITECTURE.md` | System diagram, data flow |
| `docs/API.md` | All REST + WebSocket endpoints |
| `docs/ALERTS.md` | Alert pipeline, Discord setup |
| `docs/DATABASE.md` | Schema, category classification, migrations |
| `docs/DEVELOPMENT.md` | Local setup, testing, code quality |
| `docs/FEASIBILITY.md` | Phase 0 data-source validation and rate limits |
| `docs/design/plans/` | Historical phase specifications and implementation plans |
| `frontend/AGENTS.md` | Next.js 16 breaking changes warning |
