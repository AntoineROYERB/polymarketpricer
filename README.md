# Polymarket Smart Money Tracker

![CI](https://github.com/AntoineROYERB/polymarketpricer/actions/workflows/ci.yml/badge.svg)

Identify the most skilled Polymarket traders, measure their performance by niche, detect when they open new positions, and generate actionable alerts.

> **Status:** Phase 3 — Smart Money Detection ✅ Complete (Action Classification, Alert REST API, WebSocket Streaming, Discord Delivery, Alert Testing Suite)

---

## Documentation

| Section | Description |
|---------|-------------|
| [📐 Architecture](docs/ARCHITECTURE.md) | System diagram, data flow, ETL pipelines |
| [🚀 Quick Start](#quick-start) | Get up and running in minutes |
| [🛠️ Development](docs/DEVELOPMENT.md) | Local setup, testing, code quality, environment config |
| [📖 API Reference](docs/API.md) | All REST and WebSocket endpoints |
| [🔔 Smart Money Alerts](docs/ALERTS.md) | Alert detection pipeline, Discord delivery, setup |
| [🗄️ Database Schema](docs/DATABASE.md) | Tables, category classification, migrations |
| [📁 Project Structure](#project-structure) | Directory layout |
| [📋 Phases](#phases) | Project roadmap and status |

---

## Quick Start

```bash
# Start all services
docker compose up -d

# Run database migrations
docker compose exec app alembic upgrade head

# (Optional) Seed with pre-computed data to skip ETL pipelines (~30 min)
# docker compose exec postgres psql -U app -d polymarket < docker/initdb/seed.sql.gz

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
│   │   ├── alert_service.py     # Discord delivery, action classification
│   │   ├── category_service.py  # Category leaderboards, wallet breakdown
│   │   ├── category_classifier.py  # Thin wrapper around keyword classifier
│   │   ├── leaderboard_service.py
│   │   ├── wallet_service.py
│   │   └── ws_manager.py        # WebSocket connection manager
│   ├── models/
│   │   ├── schemas.py           # Pydantic response models
│   │   └── enums.py             # TradeSide, MarketCategory
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py              # Mock DB fixtures
│       ├── test_alert_service.py    # Alert delivery service tests (39)
│       ├── test_category_classifier.py  # Phase 2 classifier unit tests
│       ├── test_ws_manager.py       # WebSocket manager tests (14)
│       ├── test_api/
│       │   ├── __init__.py
│       │   ├── test_endpoints.py
│       │   ├── test_alert_endpoints.py  # Phase 3 alert API tests (13)
│       │   └── test_category_endpoints.py  # Phase 2 category API tests
│       └── test_db_integrity.py   # 56 integration tests
│
├── alembic/                     # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial.py
│       ├── 002_category_analytics.py
│       ├── 003_add_mapped_category.py
│       ├── 004_add_categories_table.py
│       ├── 005_smart_money_alerts.py
│       ├── 006_drop_outcome_id_fks.py
│       └── 007_add_wallet_pnl_snapshots.py
│
├── mage/                        # Mage AI (bootstrapped on startup)
│   ├── Dockerfile
│   └── requirements.txt
│
├── docs/                        # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── ALERTS.md
│   ├── DATABASE.md
│   └── DEVELOPMENT.md
│
└── .opencode/
    ├── agents/                  # OpenCode agents
    ├── commands/                # Custom commands
    └── plans/                   # Phase specifications (for coding agents)
        ├── db-seed-dump.md
        ├── phase-01/
        └── phase-02/
```

---

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 0 — Feasibility Study | ✅ Complete | Data source validation, rate limits, architecture |
| 1 — MVP Leaderboard | ✅ Complete | FastAPI backend + Mage ETL pipelines |
| 2 — Niche Expertise | ✅ Complete | Category-specific rankings and specialist detection |
| 3 — Smart Money Detection | ✅ Complete | Action classification, alert rules engine, PnL cash-flow reconstruction, REST API, WebSocket stream, Discord delivery, alert testing suite |
| 4 — Edge Scoring | 📋 Planned | Predictive accuracy metrics |
| 5 — Recommendation Engine | 📋 Planned | Follow recommendations |
| 6 — Dashboard | 📋 Planned | Next.js frontend |
| 7 — Advanced Features | 📋 Planned | ML, clustering, portfolio simulation |

See [ROADMAP.md](ROADMAP.md) for full details.
