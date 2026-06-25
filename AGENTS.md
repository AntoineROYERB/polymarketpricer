# polymarketpricer

Multi-pipeline ETL system that feeds Polymarket data into PostgreSQL, served by a FastAPI backend.

## Quick Reference

```bash
# Start everything
docker compose up -d

# Run migrations
docker compose exec app alembic upgrade head

# Run all ETL pipelines
./scripts/run-all-pipelines.sh

# Run full ETL cycle via orchestration pipeline
docker compose exec mage mage run /home/src/default_repo orchestration

# Restore from seed (avoids pipelines)
docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql.gz
docker compose exec app alembic upgrade head
```

## ETL Pipelines

10 Mage AI pipelines under `magic/default_repo/pipelines/`:

| Pipeline | Loads | Transforms | Exports |
|---|---|---|---|---|
| `ingestion_market_discovery` | Gamma `/markets/keyset` | Merge active+resolved, parse outcomes | `events`, `markets`, `outcomes` |
| `ingestion_wallet_discovery` | Data API `/trades` → proxy wallets | Gamma `/users/{addr}` resolve | `wallets` |
| `ingestion_position_sync` | Data API `/positions?user=` | Diff vs previous positions | `positions`, `position_history` |
| `ingestion_pnl` | Data API `/activity` (cursor pagination) | Cash-flow PnL formula, category breakdown | `wallet_pnl_snapshots` |
| `ingestion_trade_history` | Data API `/trades?user=` | Dedup by trade id | `trades` |
| `enrichment_analytics_computation` | PG queries (recent activity) | PnL, ROI, Sharpe, win rate | `wallet_analytics` |
| `enrichment_ranking_computation` | PG queries (analytics) | Weighted score, top-100 lists | `ranking_snapshots` |
| `category_analytics` | PG queries (markets + categories) | Per-category PnL, ROI, win rate, specialist flag | `category_analytics`, `category_rankings` |
| `smart_money_detection` | PG queries (position changes, scores, rules) | Classify actions, apply score/size/liquidity thresholds | `alerts` |
| `verify_etl_output` | PG integrity checks | — | — |

Run a single pipeline:

```bash
docker compose exec mage mage run /home/src/default_repo ingestion_market_discovery

# Run full ETL cycle via orchestration pipeline
docker compose exec mage mage run /home/src/default_repo orchestration
```

## Database Seed Dump

To avoid re-running pipelines after a fresh `docker compose up`, the repo includes a
pre-computed seed at `docker/initdb/seed.sql.gz` tracked via **Git LFS**.

### Requirements

- **Git LFS**: every developer must run once:
  ```bash
  git lfs install          # one-time per machine
  git lfs pull             # after clone to get the actual dump file
  ```

### Restore from Seed

```bash
# Fresh start (destroys named volume)
docker compose down -v
docker compose up -d          # Postgres auto-loads seed.sql.gz on init
docker compose exec app alembic upgrade head

# OR into an existing volume
docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql.gz
docker compose exec app alembic upgrade head
```

### Refresh Seed

Run after pipeline executions to capture fresh data:

```bash
./scripts/refresh-seed.sh     # dumps → docker/initdb/seed.sql.gz
git add docker/initdb/seed.sql.gz
git commit -m "chore: refresh seed dump"
```

Refresh when:
- After running ETL pipelines
- After alembic schema migrations
- Before a release / PR merge
- When the seed is > 7 days old

### Troubleshooting

| Symptom | Fix |
|---|---|
| `seed.sql.gz` is a tiny text file | `git lfs pull` |
| `relation does not exist` | Run `alembic upgrade head` first |
| FK violation on restore | Seed is stale — refresh it |
| `column does not exist` | Schema mismatch — run migrations first |

## Git LFS

`docker/initdb/seed.sql.gz` is tracked via Git LFS. The `.gitattributes` file in the
repo root declares the pattern. All contributors must have `git-lfs` installed.

## Category Classification

Markets are classified into 8 target categories using a 3-tier classifier:

| Tier | Method | Description |
|------|--------|-------------|
| 1 | Raw API map | Direct mapping from API's `category` field to target category |
| 2 | Event inheritance | Inherits category from parent event when available |
| 3 | Keyword rules | 300+ keywords matched against market question text |

Categories: `politics`, `crypto`, `sports`, `economics`, `technology`, `ai`, `geopolitics`, `entertainment`

Classifier source: `magic/default_repo/utils/category_classifier.py`

## Testing

The project has four test suites:

### Unit / API Tests (40 tests)

Mock-based tests that verify endpoint behaviour without a real database:

```bash
python3 -m pytest app/tests/test_api/ -v
```

| File | Tests | What it validates |
|---|---|---|---|
| `test_endpoints.py` | 9 | Phase 1 endpoints (leaderboard, wallets, markets) |
| `test_category_endpoints.py` | 8 | Phase 2 endpoints (category leaderboards, wallet categories) |
| `test_alert_endpoints.py` | 13 | Phase 3 alert endpoints (list, filter, pagination, stats, 404/422 error handling) |
| `test_category_classifier.py` | 10 | Category classification for all 8 categories + unclassifiable + case insensitivity (at `app/tests/`) |

### Service / Unit Tests (53 tests)

Pure function and mocked-service tests:

```bash
python3 -m pytest app/tests/test_alert_service.py app/tests/test_ws_manager.py -v
```

| File | Tests | What it validates |
|---|---|---|---|
| `test_alert_service.py` | 39 | `classify_action`, `_format_action`, `send_discord_alert`, `poll_unnotified_alerts`, `mark_notified`, edge cases |
| `test_ws_manager.py` | 14 | Connection lifecycle, broadcast, heartbeat, dead connection cleanup |

### Integration Tests (real database)

`app/tests/test_db_integrity.py` connects to the actual PostgreSQL instance and validates
ETL pipeline output. Requires `docker compose up -d` (postgres service running).

```bash
# Run only integration tests
python3 -m pytest app/tests/test_db_integrity.py -m integration -v

# Run all tests (149 total)
python3 -m pytest app/tests/ -v
```

What the 56 integration tests check:

| Category | Tests | What it validates |
|---|---|---|
| Row counts | 11 | Each populated table meets a minimum row threshold |
| Referential integrity | 9 | No orphaned foreign keys across all FK relationships (incl. `wallet_pnl_snapshots`) |
| Not-null constraints | 8 | Critical columns (`question`, `price`, `timestamp`, `wallet`, analytics metrics, category analytics, pnl_snapshot keys) have no NULLs |
| Analytics quality | 7 | PNL within ±500k, win_rate in [0,1], wallet_score in [0,100], drawdown ≤ 0, profit_factor ≥ 0, category ROI/win_rate in range |
| PnL snapshot quality | 2 | `total_pnl = realized + unrealized`, PnL ≤ 100× cost basis |
| Timestamp sanity | 2 | No future timestamps in `trades` or future dates in `wallet_analytics` |
| Cross-table consistency | 5 | Analytics/trade wallets exist in `wallets`, markets have at least one outcome, category wallets exist in `wallets`, pnl_snapshot FK valid |
| ROI range (relaxed) | 1 | Category analytics ROI within [-100000, 500000] |
| **Alerts (Phase 3)** | **8** | Alerts table queryable, alert_rules global default, FK (wallet, market), NOT NULL (8 cols), score range [0,100], position_size > 0, valid action enums |
| **PnL snapshot** | 3 | Consistency, bounds, plus 1 combined with row counts |

**Note:** Integration tests use a synchronous `psycopg2` connection (not asyncpg) to avoid
concurrency issues with parametrized test functions. The sync URL is derived from
the async `DATABASE_URL` config by replacing the driver prefix.

## Project Layout

```
.
├── docker-compose.yml         # PostgreSQL + Redis + Mage + app
├── Dockerfile                 # FastAPI app image
├── requirements.txt
├── pyproject.toml
├── .gitattributes             # LFS: seed.sql.gz
├── .pre-commit-config.yaml
│
├── app/                       # FastAPI backend
│   ├── main.py
│   ├── api/                   # Routes
│   ├── db/                    # AsyncEngine + models
│   ├── services/              # Business logic
│   ├── models/                # Pydantic schemas
│   └── tests/                 # Test suites
│       ├── __init__.py
│       ├── conftest.py            # Shared mock fixtures
│       ├── test_alert_service.py  # 39 alert service tests
│       ├── test_category_classifier.py# 10 classifier unit tests
│       ├── test_ws_manager.py     # 14 WebSocket manager tests
│       ├── test_api/              # Mock-based API tests
│       │   ├── __init__.py
│       │   ├── test_endpoints.py          # 9 endpoint tests
│       │   ├── test_alert_endpoints.py # 13 Phase 3 alert endpoint tests
│       │   └── test_category_endpoints.py # 8 Phase 2 endpoint tests
│       └── test_db_integrity.py   # 56 integration tests
│
├── alembic/                   # DB migrations
│   └── versions/
│       ├── 001_initial.py
│       ├── 002_category_analytics.py
│       ├── 003_add_mapped_category.py
│       ├── 004_add_categories_table.py
│       ├── 005_smart_money_alerts.py
│       ├── 006_drop_outcome_id_fks.py
│       └── 007_add_wallet_pnl_snapshots.py
│
├── docker/
│   └── initdb/
│       ├── .gitkeep
│       └── seed.sql.gz           # LFS-tracked dump
│
├── magic/                      # Mage AI
│   ├── Dockerfile
│   └── default_repo/
│       ├── pipelines/         # 10 pipeline dirs
│       ├── data_loaders/      # 15 loaders
│       ├── transformers/      # 7 transformers
│       └── data_exporters/    # 10 exporters
│
├── scripts/
│   ├── run-all-pipelines.sh   # Bash wrapper → orchestration pipeline
│   ├── backfill_categories.py
│   ├── backfill_pnl.py        # One-shot PnL computation from /activity
│   └── refresh-seed.sh        # pg_dump → docker/initdb/seed.sql.gz
│
└── plans/
    ├── db-seed-dump.md
    ├── phase-01/
    │   ├── 01-database-redesign.md
    │   ├── 02-etl-pipelines.md
    │   ├── 03-events-population.md
    │   ├── 04-wallet-filtering.md
    │   ├── 05-mvp-leaderboard.md
    │   ├── 06-ci-cd-setup.md
    │   ├── 07-trade-history-fix.md
    │   ├── 08-pipeline-orchestration-and-verification.md
    │   └── 09-signoff.md
    └── phase-02/
        ├── 01-database-schema.md
        ├── 02-category-mapping.md
        ├── 03-etl-pipeline.md
        ├── 04-api-endpoints.md
        ├── 05-testing.md
        └── 06-signoff.md
```
