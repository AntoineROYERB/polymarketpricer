# Phase 1 — MVP Leaderboard

## Objective

Build a leaderboard of Polymarket traders ranked by demonstrated skill. Collect positions, trades, and market data from Polymarket's public APIs, compute per-wallet analytics, filter out low-activity addresses, and surface the top performers via a FastAPI backend.

---

## Data Sources

### Polymarket Gamma API (`gamma-api.polymarket.com`)

| Endpoint | Purpose | Rate Limit |
|---|---|---|
| `GET /events` | Discover events (containers of markets) | 500 req / 10s |
| `GET /markets` | Market metadata: question, category, outcomes, timestamps | 300 req / 10s |
| `GET /tags` | Category taxonomy | — |
| `GET /users/{address}` | Resolve proxy wallet for a given address | — |

All Gamma endpoints share a general pool of **4,000 req / 10s**.

### Polymarket Data API (`data-api.polymarket.com`)

| Endpoint | Purpose | Rate Limit |
|---|---|---|
| `GET /positions?user={proxyWallet}` | Current open positions (size, avgPrice, realizedPnl, cashPnl, totalBought) | 150 req / 10s |
| `GET /closed-positions?user={proxyWallet}` | Resolved positions with full PnL | 150 req / 10s |
| `GET /trades?user={proxyWallet}` | Trade history (price, shares, amount_usd, side, timestamp) | 200 req / 10s |
| `GET /activity?user={proxyWallet}` | Event history (trade, split, merge, redemption) | 150 req / 10s |
| `GET /holders?market={id}` | Discover active wallets for a market | 150 req / 10s |
| `GET /value?user={proxyWallet}` | Aggregate portfolio value | — |

All Data endpoints share a general pool of **1,000 req / 10s**.

### Polymarket CLOB API (`clob.polymarket.com`)

| Endpoint | Purpose | Rate Limit |
|---|---|---|
| `GET /price` | Current price for a market | 1,500 req / 10s |
| `GET /prices-history` | Historical prices | 1,000 req / 10s |

CLOB general pool: **9,000 req / 10s**.

### Authentication

All three APIs are fully public (no API key required). Polymarket enforces rate limits via Cloudflare sliding-window throttling (requests are delayed, not rejected, unless sustained over limit).

---

## API Client Requirements

### Rate Limiting

- Track per-endpoint usage using sliding-window counters.
- Stagger polling across wallets; do not hit all wallets in the same second.
- Implement exponential backoff when responses are delayed (throttling signal).
- Parse and respect `X-RateLimit-Remaining` headers when present.

### Pagination

- All list endpoints use cursor-based pagination (`next_cursor`).
- Never use offset-based pagination.

### Proxy Wallet Mapping

Polymarket uses Gnosis Safe proxy wallets — a user's main wallet differs from their trading wallet. The Data API expects the proxy wallet address.

- Primary mapping: `GET /users/{address}` on the Gamma API returns `proxyWallet` in the response.
- Fallback: Query `ProxyFactory` contract on Polygon.

Store both `main_wallet` and `proxy_wallet` in the `wallets` table.

---

## Database Schema

### `markets`

| Column | Type | Notes |
|---|---|---|
| `id` | `TEXT PK` | Polymarket market ID |
| `question` | `TEXT NOT NULL` | Market question (e.g. "Will X win?") |
| `category` | `TEXT` | From Gamma API tags |
| `event_slug` | `TEXT` | Human-readable event identifier |
| `outcomes` | `JSONB` | Array of outcome names (e.g. ["Yes", "No"]) |
| `created_at` | `TIMESTAMPTZ` | |
| `resolved_at` | `TIMESTAMPTZ` | Null until resolved |
| `outcome` | `TEXT` | Winning outcome, null until resolved |

Index: `(category)`, `(created_at)`.

### `trades`

| Column | Type | Notes |
|---|---|---|
| `id` | `TEXT PK` | Polymarket trade ID |
| `wallet` | `TEXT NOT NULL` | Proxy wallet address |
| `market_id` | `TEXT NOT NULL` | FK → markets.id |
| `side` | `TEXT NOT NULL` | `BUY` or `SELL` |
| `price` | `DOUBLE PRECISION NOT NULL` | |
| `shares` | `DOUBLE PRECISION NOT NULL` | |
| `amount_usd` | `DOUBLE PRECISION NOT NULL` | |
| `timestamp` | `TIMESTAMPTZ NOT NULL` | |

Indexes: `(wallet)`, `(market_id)`, `(timestamp)`.

### `wallets`

| Column | Type | Notes |
|---|---|---|
| `wallet` | `TEXT PK` | Proxy wallet address |
| `main_wallet` | `TEXT` | User's primary address (if known) |
| `first_seen` | `TIMESTAMPTZ` | When we first observed this wallet |
| `last_seen` | `TIMESTAMPTZ` | Last activity timestamp |

### `positions`

| Column | Type | Notes |
|---|---|---|
| `wallet` | `TEXT NOT NULL` | Composite PK |
| `market_id` | `TEXT NOT NULL` | Composite PK |
| `avg_entry_price` | `DOUBLE PRECISION` | |
| `shares` | `DOUBLE PRECISION` | |
| `realized_pnl` | `DOUBLE PRECISION` | PnL from partially closed positions |
| `unrealized_pnl` | `DOUBLE PRECISION` | Current open PnL |

PK: `(wallet, market_id)`.

### `wallet_analytics`

| Column | Type | Notes |
|---|---|---|
| `wallet` | `TEXT NOT NULL` | Composite PK |
| `snapshot_date` | `DATE NOT NULL` | Composite PK |
| `total_pnl` | `DOUBLE PRECISION` | |
| `roi` | `DOUBLE PRECISION` | Return on investment (percentage) |
| `win_rate` | `DOUBLE PRECISION` | 0.0 – 1.0 |
| `num_trades` | `INTEGER` | |
| `avg_position_size` | `DOUBLE PRECISION` | Mean position value in USD |
| `risk_adj_return` | `DOUBLE PRECISION` | PnL / stddev of trade outcomes |
| `avg_holding_duration` | `INTERVAL` | Mean time from entry to exit |
| `wallet_score` | `DOUBLE PRECISION` | Composite ranking score |

PK: `(wallet, snapshot_date)`.

---

## Pipeline Steps

All data ingestion is implemented as Mage AI pipelines. Each pipeline follows the pattern:

```
data_loader (HTTP → raw data) → transformer (cleanse/enrich) → data_exporter (upsert to PostgreSQL)
```

Mage handles scheduling, retries, backfills, and monitoring through its UI at port 6789.

### 1. Market Discovery (daily)

```
GET /events?closed=false  (Gamma)
  └─ for each event → GET /markets?event={id}  (Gamma)
       └─ upsert into markets table
```

Also fetch resolved markets for historical data:
```
GET /events?closed=true
```

### 2. Wallet Discovery (daily)

For each active market, discover participants:
```
GET /holders?market={market_id}  (Data API)
  └─ for each holder address → GET /users/{address}  (Gamma)
       └─ upsert wallet with proxy_wallet mapping
```

### 3. Position Sync (every 60 seconds)

For each tracked wallet:
```
GET /positions?user={proxyWallet}  (Data API)
  └─ upsert into positions table
```

Detect and log: new market entry, position increase, position decrease, full exit.

### 4. Trade History Sync (daily backfill + incremental)

For each tracked wallet:
```
GET /trades?user={proxyWallet}&cursor={cursor}  (Data API)
  └─ paginate until caught up
  └─ upsert into trades table
```

### 5. Analytics Computation (daily)

For each wallet with activity in the last 24h:

- **Total PnL** = sum of `realized_pnl` (closed positions) + sum of `unrealized_pnl` (open positions)
- **ROI** = Total PnL / Total Cost Basis × 100
- **Win Rate** = resolved positions with positive PnL / total resolved positions
- **Number of Trades** = count of trade records
- **Average Position Size** = mean of `amount_usd` across all trades
- **Risk Adjusted Return** = Total PnL / stddev(trade_pnl) (if ≥ 3 trades, else null)
- **Average Holding Duration** = mean of (exit_time - entry_time) for resolved positions

Store as a new row in `wallet_analytics`.

### 6. Wallet Filtering

Exclude wallets that do not meet all three criteria:

| Criterion | Threshold |
|---|---|
| Minimum resolved trades | 50 |
| Minimum total volume | $1,000 |
| Minimum activity history | 3 months |

Filtering is applied before ranking.

### 7. Ranking Computation (every 6 hours)

Normalize each metric to a 0–1 scale across the eligible wallet set, then compute:

```python
wallet_score = (
    0.35 * normalized_roi +
    0.25 * normalized_winrate +
    0.15 * consistency_score +
    0.15 * experience_score +
    0.10 * risk_adjusted_return
)
```

**Consistency score** = inverse of PnL volatility (lower variance → higher score).

**Experience score** = normalized log of total trade count (more trades → higher score, with diminishing returns).

### 8. Materialize Outputs

Persist three ranked lists (updated every 6 hours):

- **Top 100 Traders** — highest `wallet_score`
- **Top 10 Emerging Traders** — highest `wallet_score` among wallets with 3–6 months history
- **Top 10 Most Consistent Traders** — highest `consistency_score`

---

## API Endpoints (FastAPI)

### `GET /api/v1/leaderboard`

Returns the Top 100 traders.

Query params: `?limit=100&offset=0`

### `GET /api/v1/leaderboard/emerging`

Returns Top 10 emerging traders.

### `GET /api/v1/leaderboard/consistent`

Returns Top 10 most consistent traders.

### `GET /api/v1/wallets/{address}`

Returns wallet profile: analytics, current positions, rank.

### `GET /api/v1/markets`

Returns known markets with optional category filter.

Query params: `?category=politics&limit=50&offset=0`

---

## Response Schemas

### Leaderboard Entry

```json
{
  "rank": 1,
  "wallet": "0x...",
  "score": 85.3,
  "roi": 42.5,
  "win_rate": 0.68,
  "total_pnl": 125000.00,
  "num_trades": 342,
  "consistency_score": 0.72,
  "experience_score": 0.85
}
```

### Wallet Profile

```json
{
  "wallet": "0x...",
  "main_wallet": "0x...",
  "first_seen": "2024-01-15T00:00:00Z",
  "last_seen": "2026-06-16T00:00:00Z",
  "analytics": {
    "total_pnl": 125000.00,
    "roi": 42.5,
    "win_rate": 0.68,
    "num_trades": 342,
    "avg_position_size": 4500.00,
    "risk_adj_return": 2.1,
    "avg_holding_duration": "14 days 6 hours"
  },
  "current_positions": [
    {
      "market_id": "0x...",
      "question": "Will candidate X win?",
      "shares": 5000,
      "avg_entry_price": 0.35,
      "unrealized_pnl": 2500.00
    }
  ],
  "rank": 1
}
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| API Framework | FastAPI |
| ORM | SQLAlchemy 2.0+ (async) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Database | PostgreSQL 16 |
| Cache | Redis (rate limit tracking, position snapshots) |
| Orchestration | Mage |
| Testing | Pytest + httpx (async) |
| Containerization | Docker + Docker Compose (PostgreSQL + Redis + Mage + app) |

---

## Project Structure

```
app/
├── __init__.py
├── main.py                       # FastAPI app factory
├── config.py                     # Settings via pydantic-settings
│
├── api/
│   ├── __init__.py
│   ├── router.py                 # Main router
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── leaderboard.py        # GET /leaderboard, /emerging, /consistent
│   │   ├── wallets.py            # GET /wallets/{address}
│   │   └── markets.py            # GET /markets
│   └── dependencies.py           # DB session, cache deps
│
├── db/
│   ├── __init__.py
│   ├── engine.py                 # AsyncEngine + session factory
│   ├── models.py                 # SQLAlchemy ORM models (all 5 tables)
│   └── migrations/               # Alembic directory
│
├── services/
│   ├── __init__.py
│   ├── wallet_service.py         # Wallet data aggregation
│   └── leaderboard_service.py    # Leaderboard query logic
│
├── models/
│   ├── __init__.py
│   ├── schemas.py                # Pydantic request/response models
│   └── enums.py                  # Side, Category, etc.
│
└── tests/
    ├── __init__.py
    ├── conftest.py               # Fixtures (test DB, mock API responses)
    └── test_api/
        ├── test_leaderboard.py
        ├── test_wallets.py
        └── test_markets.py
```

---

## Development Setup

### Docker Compose

```yaml
services:
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
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  mage:
    build:
      context: ./mage
      dockerfile: Dockerfile
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://app:devpassword@postgres:5432/polymarket
      REDIS_URL: redis://redis:6379/0
    ports:
      - "6789:6789"
    volumes:
      - ./mage:/home/src
  app:
    build: .
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://app:devpassword@postgres:5432/polymarket
      REDIS_URL: redis://redis:6379/0
    ports:
      - "8000:8000"

volumes:
  postgres_data:
```

### Local Development

```
docker compose up -d postgres redis
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Mage AI

Mage bootstraps its project structure on first startup. Access the UI at `http://localhost:6789`.

Create pipelines through the UI or programmatically via Mage's Python API. Each pipeline follows the pattern:
- **Data Loader** — HTTP request to a Polymarket API endpoint with rate limiting and cursor pagination
- **Transformer** — cleanse, enrich, or compute analytics/ranking on the loaded data
- **Data Exporter** — upsert results into PostgreSQL

Schedules are configured as Mage triggers (cron expressions).

---

## Testing Requirements

Test both `app/` (FastAPI) and `mage/` (blocks) separately.

### app/ tests

| Area | What to test |
|---|---|
| **API endpoints** | Response shape, pagination, filtering, error codes, empty results |

Target: **80%+ line coverage** for `app/`.

### mage/ tests

| Area | What to test |
|---|---|
| **Data loaders** | Rate limit behavior, retry logic, cursor pagination, error handling, response parsing |
| **Transformers** | Analytics (PnL, ROI, win rate), filtering thresholds, scoring formula, normalizer, edge cases |
| **Data exporters** | Upsert logic, deduplication, batch size handling |

Use `pytest-asyncio` for async tests. Mock all external HTTP calls with `respx`.

---

## Acceptance Criteria

- [ ] Mage pipelines for market discovery, wallet discovery, position sync, trade history, analytics, and ranking are created and run successfully
- [ ] Position sync trigger runs every 60s without hitting Polymarket rate limits
- [ ] Trade history backfill completes for all tracked wallets
- [ ] Wallet analytics are computed and stored daily via Mage transformer
- [ ] Low-activity wallets are correctly filtered out in the ranking pipeline
- [ ] Top 100 leaderboard returns sorted, correct results via FastAPI
- [ ] Top 10 Emerging and Top 10 Consistent lists are populated
- [ ] All API endpoints return correct JSON response schemas
- [ ] Test suite passes with 80%+ coverage (app + mage blocks)
- [ ] Ruff passes with no errors
- [ ] MyPy (strict) passes with no errors
- [ ] Docker Compose starts all services and Mage UI is reachable on `:6789`, app on `:8000`

---

## Out of Scope (Phase 1)

- Real-time alerts / WebSocket delivery (Phase 3)
- Category-specific niche rankings (Phase 2)
- Edge scoring / predictive accuracy (Phase 4)
- Recommendation engine (Phase 5)
- Frontend dashboard (Phase 6)
- Any trading or wallet interaction
