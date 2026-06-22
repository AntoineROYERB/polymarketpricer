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
docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql
docker compose exec app alembic upgrade head
```

## ETL Pipelines

8 Mage AI pipelines under `magic/default_repo/pipelines/`:

| Pipeline | Loads | Transforms | Exports |
|---|---|---|---|---|
| `ingestion_market_discovery` | Gamma `/markets/keyset` | Merge active+resolved, parse outcomes | `events`, `markets`, `outcomes` |
| `ingestion_wallet_discovery` | Data API `/trades` → proxy wallets | Gamma `/users/{addr}` resolve | `wallets` |
| `ingestion_position_sync` | Data API `/positions?user=` | Diff vs previous positions | `positions`, `position_history` |
| `ingestion_trade_history` | Data API `/trades?user=` | Dedup by trade id | `trades` |
| `enrichment_analytics_computation` | PG queries (recent activity) | PnL, ROI, Sharpe, win rate | `wallet_analytics` |
| `enrichment_ranking_computation` | PG queries (analytics) | Weighted score, top-100 lists | `ranking_snapshots` |
| `category_analytics` | PG queries (markets + categories) | Per-category PnL, ROI, win rate, specialist flag | `category_analytics`, `category_rankings` |
| `verify_etl_output` | PG integrity checks | — | — |

Run a single pipeline:

```bash
docker compose exec mage mage run /home/src/default_repo ingestion_market_discovery

# Run full ETL cycle via orchestration pipeline
docker compose exec mage mage run /home/src/default_repo orchestration
```

## Database Seed Dump

To avoid re-running pipelines after a fresh `docker compose up`, the repo includes a
pre-computed seed at `docker/initdb/seed.sql` tracked via **Git LFS**.

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
docker compose up -d          # Postgres auto-loads seed.sql on init
docker compose exec app alembic upgrade head

# OR into an existing volume
docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql
docker compose exec app alembic upgrade head
```

### Refresh Seed

Run after pipeline executions to capture fresh data:

```bash
./scripts/refresh-seed.sh     # dumps → docker/initdb/seed.sql
git add docker/initdb/seed.sql
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
| `seed.sql` is a tiny text file | `git lfs pull` |
| `relation does not exist` | Run `alembic upgrade head` first |
| FK violation on restore | Seed is stale — refresh it |
| `column does not exist` | Schema mismatch — run migrations first |

## Git LFS

`docker/initdb/seed.sql` is tracked via Git LFS. The `.gitattributes` file in the
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

The project has three test suites:

### Unit / API Tests (27 tests)

Mock-based tests that verify endpoint behaviour without a real database:

```bash
python3 -m pytest app/tests/test_api/ app/tests/test_category_classifier.py -v
```

| File | Tests | What it validates |
|---|---|---|---|
| `test_endpoints.py` | 9 | Phase 1 endpoints (leaderboard, wallets, markets) |
| `test_category_endpoints.py` | 8 | Phase 2 endpoints (category leaderboards, wallet categories) |
| `test_category_classifier.py` | 10 | Category classification for all 8 categories + unclassifiable + case insensitivity (at `app/tests/`) |

### Integration Tests (real database)

`app/tests/test_db_integrity.py` connects to the actual PostgreSQL instance and validates
ETL pipeline output. Requires `docker compose up -d` (postgres service running).

```bash
# Run only integration tests
python3 -m pytest app/tests/test_db_integrity.py -m integration -v

# Run all tests (70 total)
python3 -m pytest app/tests/ -v
```

What the 42 integration tests check:

| Category | Tests | What it validates |
|---|---|---|
| Row counts | 7 | Each populated table meets a minimum row threshold |
| Empty tables | 1 | `position_history` remains empty |
| Referential integrity | 8 | No orphaned foreign keys across all FK relationships |
| Not-null constraints | 6 | Critical columns (`question`, `price`, `timestamp`, `wallet`, analytics metrics, category analytics) have no NULLs |
| Analytics quality | 7 | PNL within ±500k, win_rate in [0,1], wallet_score in [0,100], drawdown ≤ 0, profit_factor ≥ 0, category ROI/win_rate in range |
| Timestamp sanity | 2 | No future timestamps in `trades` or future dates in `wallet_analytics` |
| Cross-table consistency | 4 | Analytics/trade wallets exist in `wallets`, markets have at least one outcome, category wallets exist in `wallets` |

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
├── .gitattributes             # LFS: seed.sql
├── .pre-commit-config.yaml
│
├── app/                       # FastAPI backend
│   ├── main.py
│   ├── api/                   # Routes
│   ├── db/                    # AsyncEngine + models
│   ├── services/              # Business logic
│   ├── models/                # Pydantic schemas
│   └── tests/                 # Test suites
│       ├── test_api/              # Mock-based API tests
│       │   ├── __init__.py
│       │   ├── test_endpoints.py          # 9 endpoint tests
│       │   ├── test_category_endpoints.py # 8 Phase 2 endpoint tests
│       │   └── test_category_classifier.py# 10 classifier unit tests
│       ├── __init__.py
│       ├── conftest.py            # Shared mock fixtures
│       └── test_db_integrity.py   # 33 integration tests
│
├── alembic/                   # DB migrations
│   └── versions/
│       ├── 001_initial.py
│       ├── 002_category_analytics.py
│       ├── 003_add_mapped_category.py
│       └── 004_add_categories_table.py
│
├── docker/
│   └── initdb/
│       ├── .gitkeep
│       └── seed.sql           # LFS-tracked dump
│
├── magic/                      # Mage AI
│   ├── Dockerfile
│   └── default_repo/
│       ├── pipelines/         # 8 pipeline dirs
│       ├── data_loaders/      # 13 loaders
│       ├── transformers/      # 6 transformers
│       └── data_exporters/    # 8 exporters
│
├── scripts/
│   ├── run-all-pipelines.sh   # Bash wrapper → orchestration pipeline
│   ├── backfill_categories.py
│   └── refresh-seed.sh        # pg_dump → docker/initdb/seed.sql
│
└── plans/
    ├── db-seed-dump.md
    └── trade-history-fix.md
```
