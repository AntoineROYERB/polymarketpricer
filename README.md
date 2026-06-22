# Polymarket Smart Money Tracker

![CI](https://github.com/AntoineROYERB/polymarketpricer/actions/workflows/ci.yml/badge.svg)

Identify the most skilled Polymarket traders, measure their performance by niche, detect when they open new positions, and generate actionable alerts.

> **Status:** Phase 2 — Niche Expertise Detection ✅ Complete (FastAPI backend + Mage AI pipelines)

---

## Architecture

```mermaid
flowchart LR
    subgraph APIs["External APIs"]
        GAMMA["Gamma API<br/>(markets, events, wallets)"]
        DATA["Data API<br/>(trades, positions)"]
    end

    subgraph ETL["Mage AI ETL — 7 Pipelines"]
        MD["ingestion_market_discovery<br/>markets + events + outcomes"]
        WD["ingestion_wallet_discovery<br/>proxy → main wallet"]
        TH["ingestion_trade_history<br/>per-wallet trades"]
        PS["ingestion_position_sync<br/>current positions"]
        AC["enrichment_analytics_computation<br/>PnL, ROI, Sharpe, filtering"]
        RC["enrichment_ranking_computation<br/>top-100 / emerging / consistent"]
        CA["category_analytics<br/>per-category metrics + specialists"]
    end

    subgraph DB["PostgreSQL"]
        MKT[(markets)]
        EVT[(events)]
        OUTC[(outcomes)]
        WAL[(wallets)]
        TRD[(trades)]
        POS[(positions)]
        WA[(wallet_analytics)]
        RS[(ranking_snapshots)]
        CAT[(categories)]
        CAnalytics[(category_analytics)]
        CRankings[(category_rankings)]
    end

    subgraph API["FastAPI — Port 8000"]
        LB["GET /leaderboard<br/>GET /leaderboard/emerging<br/>GET /leaderboard/consistent"]
        WP["GET /wallets/{address}"]
        MK["GET /markets"]
        CLB["GET /leaderboard/{category}<br/>GET /leaderboard/{category}/specialists"]
        WC["GET /wallets/{address}/categories<br/>GET /wallets/{address}/categories/{category}"]
    end

    GAMMA --> MD
    GAMMA --> WD
    DATA --> TH
    DATA --> PS
    MD --> MKT & EVT & OUTC
    WD --> WAL
    TH --> TRD
    PS --> POS
    MKT & EVT & OUTC & WAL & TRD & POS --> AC
    AC --> WA
    WA --> RC
    RC --> RS
    MKT --> CAT
    MKT & WAL & CAT --> CA
    CA --> CAnalytics & CRankings
    MKT & WAL & WA & RS --> LB
    WAL & WA & POS --> WP
    MKT --> MK
    CRankings & CAnalytics --> CLB
    CAnalytics & WAL --> WC
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

The **70 tests** (27 API + 43 integration) validate row counts, referential integrity,
not-null constraints, data quality ranges, timestamp sanity, cross-table consistency,
and data filtering — with all CI checks enforced via GitHub Actions (`mypy --strict` + `ruff`).

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
│   │       ├── markets.py       # GET /markets
│   │       └── categories.py    # GET /categories, /leaderboard/{category}, /wallets/{addr}/categories
│   ├── db/
│   │   ├── engine.py            # AsyncEngine + session factory
│   │   └── models.py            # SQLAlchemy ORM (10 tables)
│   ├── services/
│   │   ├── leaderboard_service.py
│   │   ├── wallet_service.py
│   │   ├── category_service.py  # Category leaderboards, wallet breakdown
│   │   └── category_classifier.py  # Thin wrapper around keyword classifier
│   ├── models/
│   │   ├── schemas.py           # Pydantic response models
│   │   └── enums.py             # TradeSide, MarketCategory
│   └── tests/
│       ├── conftest.py          # Mock DB fixtures
│       └── test_api/
│           ├── test_endpoints.py
│           ├── test_category_endpoints.py  # Phase 2 category API tests
│           └── test_category_classifier.py # Phase 2 classifier unit tests
│
├── alembic/                     # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial.py
│       ├── 002_category_analytics.py
│       ├── 003_add_mapped_category.py
│       └── 004_add_categories_table.py
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

### `GET /api/v1/categories`

List all 8 market categories with their labels.

### `GET /api/v1/leaderboard/{category}`

Top traders in a specific category, ranked by skill score.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `category` | string | — | One of `politics`, `crypto`, `sports`, `economics`, `technology`, `ai`, `geopolitics`, `entertainment` |
| `limit` | int | 50 | Results per page (max 200) |
| `offset` | int | 0 | Pagination offset |

**Example response:**

```json
{
  "category": "politics",
  "data": [
    {
      "rank": 1,
      "wallet": "0x17e5...",
      "wallet_score": 0.85,
      "roi": 41.29,
      "win_rate": 0.62,
      "total_pnl": 37053.07,
      "num_trades": 840,
      "total_volume": 89730.34,
      "is_specialist": true
    }
  ],
  "limit": 50,
  "offset": 0
}
```

### `GET /api/v1/leaderboard/{category}/specialists`

Specialist traders in a category (wallets with >30 trades and above-median ROI).

Same response shape as the main category leaderboard, filtered to specialists only.

### `GET /api/v1/wallets/{address}/categories`

Per-category performance breakdown for a wallet.

**Example response:**

```json
{
  "wallet": "0x17e5...",
  "categories": [
    {
      "category": "politics",
      "num_trades": 840,
      "total_volume": 89730.34,
      "total_pnl": 37053.07,
      "roi": 41.29,
      "win_rate": 0.62,
      "profit_factor": 3.21,
      "avg_position_size": 106.82,
      "is_specialist": true,
      "category_rank": 1
    }
  ]
}
```

### `GET /api/v1/wallets/{address}/categories/{category}`

Detailed analytics for a specific wallet+category combination.

**Example response:**

```json
{
  "wallet": "0x17e5...",
  "category": "politics",
  "num_trades": 840,
  "total_volume": 89730.34,
  "total_cost_basis": 52300.00,
  "total_pnl": 37053.07,
  "total_realized_pnl": 28000.00,
  "total_unrealized_pnl": 9053.07,
  "roi": 41.29,
  "win_rate": 0.62,
  "profit_factor": 3.21,
  "avg_position_size": 106.82,
  "avg_holding_duration": "7 days, 3:42:00",
  "is_specialist": true,
  "category_rank": 1
}
```

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `markets` | Market metadata (question, category, outcomes, resolution) |
| `trades` | Individual trade records (wallet, market, side, price, shares) |
| `wallets` | Wallet identity with proxy wallet mapping |
| `positions` | Current open positions (avg entry, shares, PnL) |
| `wallet_analytics` | Daily snapshots of computed metrics and ranking scores |
| `category_analytics` | Per-wallet, per-category PnL, ROI, win rate, specialist flags |
| `category_rankings` | Top-50 rankings per category (+ specialist lists) |
| `categories` | Lookup table for the 8 target categories |

---

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0 — Feasibility Study | ✅ Complete | Data source validation, rate limits, architecture |
| 1 — MVP Leaderboard | ✅ Complete | FastAPI backend + Mage ETL pipelines |
| 2 — Niche Expertise | ✅ Complete | Category-specific rankings and specialist detection |
| 3 — Smart Money Detection | 📋 Planned | Real-time alerts via Telegram/Discord |
| 4 — Edge Scoring | 📋 Planned | Predictive accuracy metrics |
| 5 — Recommendation Engine | 📋 Planned | Follow recommendations |
| 6 — Dashboard | 📋 Planned | Next.js frontend |
| 7 — Advanced Features | 📋 Planned | ML, clustering, portfolio simulation |

See [ROADMAP.md](ROADMAP.md) for full details.
