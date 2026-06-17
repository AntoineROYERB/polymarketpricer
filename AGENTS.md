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

# Restore from seed (avoids pipelines)
docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql
docker compose exec app alembic upgrade head
```

## ETL Pipelines

6 Mage AI pipelines under `magic/default_repo/pipelines/`:

| Pipeline | Loads | Transforms | Exports |
|---|---|---|---|
| `market_discovery` | Gamma `/markets/keyset` | Merge active+resolved, parse outcomes | `events`, `markets`, `outcomes` |
| `wallet_discovery` | Data API `/trades` → proxy wallets | Gamma `/users/{addr}` resolve | `wallets` |
| `position_sync` | Data API `/positions?user=` | Diff vs previous positions | `positions`, `position_history` |
| `trade_history` | Data API `/trades?user=` | Dedup by trade id | `trades` |
| `analytics_computation` | PG queries (recent activity) | PnL, ROI, Sharpe, win rate | `wallet_analytics` |
| `ranking_computation` | PG queries (analytics) | Weighted score, top-100 lists | `ranking_snapshots` |

Run a single pipeline:

```bash
docker compose exec mage python /home/src/scripts/run_all.py market_discovery
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
│   └── models/                # Pydantic schemas
│
├── alembic/                   # DB migrations
│   └── versions/
│       └── 001_initial.py
│
├── docker/
│   └── initdb/
│       ├── .gitkeep
│       └── seed.sql           # LFS-tracked dump
│
├── magic/                      # Mage AI
│   ├── Dockerfile
│   └── default_repo/
│       ├── pipelines/         # 6 pipeline dirs
│       ├── data_loaders/      # 13 loaders
│       ├── transformers/      # 6 transformers
│       └── data_exporters/    # 7 exporters
│
├── scripts/
│   ├── run_all.py             # Sequential pipeline runner
│   ├── run-all-pipelines.sh   # Bash wrapper
│   └── refresh-seed.sh        # pg_dump → docker/initdb/seed.sql
│
└── plans/
    └── db-seed-dump.md        # This plan
```
