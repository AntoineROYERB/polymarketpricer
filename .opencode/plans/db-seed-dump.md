# Database Seed Dump Management

Seed the PostgreSQL database from a pre-computed `pg_dump` so the app can start with real data
without re-running all 6 ETL pipelines (~30 min).

---

## Setup

### 1. Install Git LFS

```bash
# macOS
brew install git-lfs

# Linux
apt install git-lfs       # Debian
yum install git-lfs       # RHEL

# Init (one-time per user)
git lfs install
```

The dump file (`docker/initdb/seed.sql`) is tracked via Git LFS so it stays out of the
regular git history. A `.gitattributes` file in the repo root marks it.

### 2. Files to Create

| File | Purpose |
|---|---|
| `.gitattributes` | LFS tracking rule for `seed.sql` |
| `docker/initdb/.gitkeep` | Keep the initdb directory in git |
| `docker/initdb/seed.sql` | Actual dump (tracked by LFS) |
| `scripts/refresh-seed.sh` | Wrapper to re-dump + commit |

### 3. Files to Modify

| File | Change |
|---|---|
| `docker-compose.yml` | Add initdb volume mount to `postgres` service |
| `AGENTS.md` | Document the dump workflow |
| `README.md` | Add seed-restore step to Quick Start |

---

## Implementation Steps

### Step 1 — Create `.gitattributes`

Create `/Users/antoine/Git/polymarketpricer/.gitattributes`:

```
docker/initdb/seed.sql filter=lfs diff=lfs merge=lfs -text
```

Then stage the pattern:

```bash
git lfs track "docker/initdb/seed.sql"
```

### Step 2 — Prepare Directories

```bash
mkdir -p docker/initdb
touch docker/initdb/.gitkeep
```

### Step 3 — Generate the Dump

```bash
docker compose exec -T postgres pg_dump \
  -U app -d polymarket \
  --no-owner --no-acl \
  --exclude-table-data='alembic_version' \
  > docker/initdb/seed.sql
```

> **Exclude `alembic_version`** so schema migrations are still run normally.
> The dump contains only application data (markets, outcomes, wallets, positions, etc.)

### Step 4 — Mount in docker-compose.yml

Edit the `postgres` service in `docker-compose.yml`:

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: polymarket
    POSTGRES_USER: app
    POSTGRES_PASSWORD: devpassword
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./docker/initdb:/docker-entrypoint-initdb.d    # ← add this line
```

PostgreSQL automatically executes `.sql` files from `/docker-entrypoint-initdb.d/`
**on first start only** (when the data directory is empty). Subsequent restarts with
an existing volume will skip the seed.

### Step 5 — Create Refresh Script

Create `/Users/antoine/Git/polymarketpricer/scripts/refresh-seed.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Dumping database to docker/initdb/seed.sql ..."
docker compose exec -T postgres pg_dump \
  -U app -d polymarket \
  --no-owner --no-acl \
  --exclude-table-data='alembic_version' \
  > docker/initdb/seed.sql

echo "Done.  $(wc -c < docker/initdb/seed.sql) bytes written."
echo ""
echo "Next steps:"
echo "  git add docker/initdb/seed.sql"
echo "  git commit -m \"chore: refresh seed dump\""
```

Make it executable:

```bash
chmod +x scripts/refresh-seed.sh
```

### Step 6 — Stage with LFS

```bash
git add .gitattributes docker/initdb/
git lfs ls-files --all    # verify seed.sql is tracked by LFS
git commit -m "chore: add database seed dump with LFS"
```

---

## Launch Workflow

### Fresh start (first clone or after `docker compose down -v`)

PostgreSQL automatically runs `seed.sql` on container init:

```bash
docker compose down -v       # wipe the named volume
docker compose up -d         # Postgres creates DB, runs seed.sql
docker compose exec app alembic upgrade head   # bring schema current
```

### Restore into an existing volume

```bash
docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql
docker compose exec app alembic upgrade head
```

---

## Refresh Workflow

Run after any pipeline execution to capture fresh data:

```bash
./scripts/refresh-seed.sh
git add docker/initdb/seed.sql
git commit -m "chore: refresh seed dump"
```

---

## When to Refresh the Seed

| Scenario | Action |
|---|---|
| After running ETL pipelines | `./scripts/refresh-seed.sh` |
| After alembic schema migration | Refresh seed (columns may have changed) |
| Before a release / PR merge | Refresh so reviewers have realistic data |
| When seed is > 7 days old | Refresh to avoid stale price/PnL data |

---

## Trade-offs & Notes

- **Size**: ~28 MB as of June 2026. Tracked via Git LFS — regular clones get a pointer
  (< 200 bytes), LFS pulls the actual content. Add `git lfs pull` to CI steps.
- **LFS requirement**: Every developer must run `git lfs install` once and
  `git lfs pull` after clone. Documented in AGENTS.md.
- **Schema staleness**: If alembic adds a NOT NULL column after the seed was generated,
  `psql restore` will fail. Always run `alembic upgrade head` after seeding.
- **Staging/Prod**: Seeds are for dev/CI only. In production, run pipelines on a schedule
  and use volume snapshots for backup.
- **LFS bandwidth**: Free tier on GitHub is 1 GB/month storage, 1 GB/month bandwidth.
  A 28 MB dump will use ~28 MB of storage per revision. Compress with `gzip` if needed.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `git: 'lfs' is not a git command` | Git LFS not installed | `brew install git-lfs && git lfs install` |
| `seed.sql` is a tiny text file instead of SQL | LFS pointer not resolved | `git lfs pull` |
| `relation "markets" does not exist` | Alembic not run | `docker compose exec app alembic upgrade head` |
| `column "condition_id" does not exist` | Seed too old, schema changed | Refresh seed or run migrations first |
| `pg_dump: error: too many clients` | Connection leak | Wait or restart postgres container |
