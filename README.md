# Polymarket Smart Money Tracker

Identify the most skilled Polymarket traders, measure their performance by niche, detect when they open new positions, and generate actionable alerts.

> **Status:** Phase 1 — MVP Leaderboard (FastAPI backend + Mage AI pipelines)

---

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│  Gamma API  │    │  Data API   │    │  CLOB API    │
│  (metadata) │    │ (positions, │    │  (prices)    │
│             │    │  trades)    │    │              │
└──────┬──────┘    └──────┬──────┘    └──────┬───────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                    ┌─────▼─────┐
                    │  Mage AI  │  Port 6789
                    │ (ETL)     │
                    └─────┬─────┘
                          │ writes
                    ┌─────▼─────┐
                    │PostgreSQL │
                    └─────┬─────┘
                          │ reads
                    ┌─────▼─────┐
                    │  FastAPI  │  Port 8000
                    │ (backend) │
                    └───────────┘
```

---

## Quick Start

```bash
# Start all services
docker compose up -d

# Run database migrations
docker compose exec app alembic upgrade head

# (Optional) Seed with pre-computed data to skip ETL pipelines (~30 min)
# docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql

# Check health
curl http://localhost:8000/health

# Browse API
curl http://localhost:8000/api/v1/leaderboard
curl http://localhost:8000/api/v1/markets
curl http://localhost:8000/api/v1/wallets/0x...
curl http://localhost:8000/docs
```

Then open **Mage AI** at `http://localhost:6789` to create ETL pipelines that pull data from Polymarket APIs into PostgreSQL.

---

## Services

| Service | Port | Description |
|---------|------|-------------|
| **FastAPI** | `8000` | REST API for leaderboard, wallets, markets |
| **Mage AI** | `6789` | ETL orchestration (data loaders → transformers → exporters) |
| **PostgreSQL** | `5432` | Primary database |
| **Redis** | `6379` | Cache and rate-limit tracking |

---

## Development

### Prerequisites

- Python 3.12+
- Docker & Docker Compose

### Local Setup

```bash
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

### Testing

The project has two test suites:

```bash
# Unit / API tests (mocked, no Docker needed)
python -m pytest app/tests/test_api/ -v

# Integration tests (requires docker compose up -d)
python -m pytest app/tests/test_db_integrity.py -m integration -v

# Run all tests
python -m pytest app/tests/ -v

# With coverage
python -m pytest app/tests/ --cov=app -v
```

The **32 integration tests** validate row counts, referential integrity,
not-null constraints, data quality ranges, timestamp sanity, and
cross-table consistency across all ETL tables.

### Code Quality

```bash
# Lint
ruff check app/

# Type check
mypy app/ --strict

# Pre-commit (install once)
pre-commit install
pre-commit run --all-files
```

---

## Project Structure

```
.
├── docker-compose.yml           # PostgreSQL + Redis + Mage + app
├── Dockerfile                   # FastAPI app image
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Ruff, MyPy, Pytest config
├── .pre-commit-config.yaml      # Pre-commit hooks
│
├── app/                         # FastAPI backend
│   ├── main.py                  # App factory, /health endpoint
│   ├── config.py                # pydantic-settings
│   ├── api/
│   │   ├── router.py            # Route aggregation
│   │   ├── dependencies.py      # DB session dependency
│   │   └── v1/
│   │       ├── leaderboard.py   # GET /leaderboard, /emerging, /consistent
│   │       ├── wallets.py       # GET /wallets/{address}
│   │       └── markets.py       # GET /markets
│   ├── db/
│   │   ├── engine.py            # AsyncEngine + session factory
│   │   └── models.py            # SQLAlchemy ORM (5 tables)
│   ├── services/
│   │   ├── leaderboard_service.py
│   │   └── wallet_service.py
│   ├── models/
│   │   ├── schemas.py           # Pydantic response models
│   │   └── enums.py             # TradeSide, MarketCategory
│   └── tests/
│       ├── conftest.py          # Mock DB fixtures
│       └── test_api/
│           └── test_endpoints.py
│
├── alembic/                     # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/001_initial.py
│
├── mage/                        # Mage AI (bootstrapped on startup)
│   ├── Dockerfile
│   └── requirements.txt
│
└── .opencode/
    ├── agents/                  # OpenCode agents
    ├── commands/                # Custom commands
    └── plans/                   # Phase specifications (for coding agents)
        └── phase-01-mvp-leaderboard.md
```

---

## API Reference

### `GET /health`

Health check.

### `GET /api/v1/leaderboard`

Top 100 traders ranked by skill score.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 100 | Results per page (max 500) |
| `offset` | int | 0 | Pagination offset |

### `GET /api/v1/leaderboard/emerging`

Top 10 emerging traders.

### `GET /api/v1/leaderboard/consistent`

Top 10 most consistent traders.

### `GET /api/v1/wallets/{address}`

Full wallet profile with analytics and current positions.

### `GET /api/v1/markets`

List known markets.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `category` | string | — | Filter by category |
| `limit` | int | 50 | Results per page (max 500) |
| `offset` | int | 0 | Pagination offset |

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `markets` | Market metadata (question, category, outcomes, resolution) |
| `trades` | Individual trade records (wallet, market, side, price, shares) |
| `wallets` | Wallet identity with proxy wallet mapping |
| `positions` | Current open positions (avg entry, shares, PnL) |
| `wallet_analytics` | Daily snapshots of computed metrics and ranking scores |

---

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0 — Feasibility Study | ✅ Complete | Data source validation, rate limits, architecture |
| 1 — MVP Leaderboard | 🚧 In progress | FastAPI backend + Mage ETL pipelines |
| 2 — Niche Expertise | 📋 Planned | Category-specific rankings |
| 3 — Smart Money Detection | 📋 Planned | Real-time alerts via Telegram/Discord |
| 4 — Edge Scoring | 📋 Planned | Predictive accuracy metrics |
| 5 — Recommendation Engine | 📋 Planned | Follow recommendations |
| 6 — Dashboard | 📋 Planned | Next.js frontend |
| 7 — Advanced Features | 📋 Planned | ML, clustering, portfolio simulation |

See [ROADMAP.md](ROADMAP.md) for full details.
