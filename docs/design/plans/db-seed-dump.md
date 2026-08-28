# Database Seed Snapshot

The repository ships a small snapshot of the production database at
`docker/initdb/seed.sql.gz`, so `docker compose up` yields a populated instance without
running the ETL pipelines (~30 min) or reaching the Polymarket APIs — which are
geo-blocked in some countries, France included.

## Why a *sampled* snapshot

The first version of this file was a full `pg_dump` (367 MB, 11.6M trades) tracked with
Git LFS. That does not belong in a public repository: GitHub's free LFS tier allows 1 GB
of storage and 1 GB of bandwidth per month, so a handful of clones exhausts the quota and
every subsequent clone fails.

The snapshot is now a foreign-key-consistent *sample*, ~3 MB gzipped, stored in plain
git. Git LFS is no longer used anywhere in the repository.

## Contents

| Slice | Rule |
|---|---|
| `wallets` | 200 highest `wallet_score` from the latest analytics snapshot, plus any followed wallet |
| `trades` | 120 most recent trades per sampled wallet (~24k rows) |
| `markets` / `events` / `outcomes` | Everything referenced by the sampled trades |
| `positions` | Sampled wallets, restricted to sampled markets |
| Analytics tables | All rows for sampled wallets: `wallet_analytics`, `ranking_snapshots`, `category_analytics`, `category_rankings`, `wallet_pnl_snapshots`, `wallet_edge_snapshots`, `wallet_category_follow_scores` |
| `alert_rules` | Global default rule; `discord_webhook_url` blanked |
| `wallet_follows`, paper-trading tables | Excluded — user data, not reference data |

The dump is a schema-only `pg_dump` followed by `COPY` blocks, wrapped in
`session_replication_role = replica` so FK order does not matter during restore. The
`alembic_version` row is written last, so `alembic upgrade head` is a no-op on a freshly
seeded database and still applies any migration added afterwards.

## Regenerating

Requires a running, populated local stack:

```bash
docker compose up -d
./scripts/run-all-pipelines.sh    # or restore your own dump
./scripts/make-sample-seed.sh     # writes docker/initdb/seed.sql.gz
```

Verify before committing:

```bash
docker run -d --name seedtest -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app \
  -e POSTGRES_DB=polymarket -p 55432:5432 postgres:16-alpine
gunzip -c docker/initdb/seed.sql.gz | docker exec -i seedtest \
  psql -U app -d polymarket -v ON_ERROR_STOP=1
DATABASE_URL=postgresql+asyncpg://app:app@localhost:55432/polymarket API_KEY=test \
  python -m pytest app/tests -m integration
docker rm -f seedtest
```

Keep the file under ~5 MB. If a change makes it grow, tighten the per-wallet trade cap in
`scripts/make-sample-seed.sh` rather than reaching for Git LFS.

## Consumers

- **`docker-compose.yml`** mounts `docker/initdb/` into the postgres container's
  `/docker-entrypoint-initdb.d`, which runs `.sql.gz` files on first boot only. Drop the
  `postgres_data` volume to re-seed.
- **CI** (`.github/workflows/ci.yml`) restores the same file into a service container
  before the integration suite, so CI and local development assert against identical data.
