# Phase 1 — Database Schema Redesign

> **Goal**: Normalize, enrich, and future-proof the schema before ETL pipelines are built.
> **Strategy**: Full redesign now (zero production data) — single squashed migration.
> **Status**: Planning — ready for implementation.

---

## 1. Why Change the Schema?

The current schema (commit `3ef3393`) has gaps that prevent correct analytics and ranking:

| Problem | Impact |
|---|---|
| `markets.outcomes` is a JSON text blob | Can't query per-outcome positions or prices |
| No `events` table | Can't do category-level analysis |
| `trades` lacks `fee_usd` | PnL overstated by 1–3% (Polymarket fees) |
| `positions` lacks `entry_time`, `exit_time`, `status` | Holding duration requires complex join; can't filter by open/closed/resolved |
| `wallets` has no `is_tracked` flag | Can't pause tracking for broken/spam wallets |
| `wallet_analytics` lacks `total_volume`, `sharpe_ratio`, `profit_factor`, `max_drawdown` | Filtering and ranking miss standard metrics |
| No foreign keys | Data integrity relies entirely on pipeline correctness |
| `Numeric` without precision | Performance cost on large aggregations |

---

## 2. Target Schema — Final Tables

### `events` (NEW)

```python
class Event(Base):
    __tablename__ = "events"
    id            = Column(Text, primary_key=True)
    title         = Column(Text, nullable=False)
    slug          = Column(Text, nullable=True)
    category      = Column(Text, nullable=True)
    start_date    = Column(DateTime(timezone=True), nullable=True)
    end_date      = Column(DateTime(timezone=True), nullable=True)
    closed        = Column(Boolean, nullable=False, default=False)
```

Groups markets into real-world events ("US Election 2024"). Enables category-level aggregation in analytics.

---

### `markets` (ENRICHED)

| Column | Type | Change |
|---|---|---|
| `id` | Text PK | — |
| `question` | Text, NOT NULL | — |
| `category` | Text | — |
| `event_id` | Text → FK → events.id | **NEW** — links market to parent event |
| `event_slug` | Text | — |
| `volume_usd` | Numeric(28, 2) | **NEW** — total volume for filtering |
| `liquidity_usd` | Numeric(28, 2) | **NEW** — current liquidity |
| `close_time` | DateTime(tz) | **NEW** — when trading ends |
| `created_at` | DateTime(tz) | — |
| `resolved_at` | DateTime(tz) | — |
| `winning_outcome` | Text | renamed from `outcome` |
| `outcomes` | *(removed)* | → moved to `outcomes` table |

Indexes: `(category)`, `(created_at)`, `(event_id)`.

---

### `outcomes` (NEW — replaces `markets.outcomes` JSON blob)

```python
class Outcome(Base):
    __tablename__ = "outcomes"
    id        = Column(Text, primary_key=True)
    market_id = Column(Text, ForeignKey("markets.id"), nullable=False)
    label     = Column(Text, nullable=False)    # "Yes", "No", "Candidate A"
    price     = Column(Numeric(28, 12), nullable=True)
    winner    = Column(Boolean, nullable=True)  # NULL until resolved
```

Why: Queries like "which wallets bought the winning outcome on market X" or "what's the average price of NO across all markets" become trivial SQL instead of JSON parsing.

Index: `(market_id)`.

---

### `wallets` (ENRICHED)

| Column | Type | Change |
|---|---|---|
| `wallet` | Text PK | — |
| `main_wallet` | Text | — |
| `label` | Text | **NEW** — manual tag ("whale", "bot", "manual") |
| `is_tracked` | Boolean, default True | **NEW** — enable/disable tracking |
| `first_seen` | DateTime(tz) | — |
| `last_seen` | DateTime(tz) | — |
| `last_position_sync` | DateTime(tz) | **NEW** — for differential sync |
| `last_trade_sync` | DateTime(tz) | **NEW** — for differential sync |

Index: `(is_tracked)`.

---

### `trades` (ENRICHED)

| Column | Type | Change |
|---|---|---|
| `id` | Text PK | — |
| `wallet` | Text → FK → wallets.wallet | FK added |
| `market_id` | Text → FK → markets.id | FK added |
| `outcome_id` | Text → FK → outcomes.id | **NEW** — which outcome was traded |
| `side` | Enum("BUY","SELL") | **tightened** from free text |
| `type` | Enum("MARKET","LIMIT") | **NEW** — order type |
| `price` | Numeric(28, 12) | precision specified |
| `shares` | Numeric(28, 12) | precision specified |
| `amount_usd` | Numeric(28, 12) | precision specified |
| `fee_usd` | Numeric(28, 12) | **NEW** — Polymarket fee |
| `timestamp` | DateTime(tz) | — |
| `tx_hash` | Text | **NEW** — for auditability |

Indexes: `(wallet, timestamp DESC)`, `(market_id)`, `(timestamp)`.

---

### `positions` (ENRICHED)

| Column | Type | Change |
|---|---|---|
| `wallet` | Text → FK → wallets.wallet | PK, FK |
| `market_id` | Text → FK → markets.id | PK, FK |
| `outcome_id` | Text → FK → outcomes.id | **NEW** |
| `side` | Enum("BUY","SELL") | **NEW** |
| `status` | Enum("OPEN","CLOSED","RESOLVED"), default "OPEN" | **NEW** |
| `avg_entry_price` | Numeric(28, 12) | precision |
| `shares` | Numeric(28, 12) | precision |
| `entry_time` | DateTime(tz) | **NEW** — first detected entry |
| `exit_time` | DateTime(tz) | **NEW** — last detected exit |
| `realized_pnl` | Numeric(28, 12) | precision |
| `unrealized_pnl` | Numeric(28, 12) | precision |
| `total_pnl` | Numeric(28, 12) | **NEW** — realized + unrealized |

Why `entry_time`/`exit_time`: `avg_holding_duration` can be computed as a direct `AVG(exit_time - entry_time)` instead of a complex multi-table join.

---

### `wallet_analytics` (ENRICHED)

| Column | Type | Change |
|---|---|---|
| `wallet` | Text → FK → wallets.wallet | PK |
| `snapshot_date` | Date | PK |
| `total_pnl` | Numeric(28, 2) | — |
| `total_realized_pnl` | Numeric(28, 2) | **NEW** |
| `total_unrealized_pnl` | Numeric(28, 2) | **NEW** |
| `roi` | Numeric(8, 6) | — |
| `total_volume` | Numeric(28, 2) | **NEW** — sum of \|amount_usd\| |
| `total_cost_basis` | Numeric(28, 2) | **NEW** — sum of cost for all positions |
| `win_rate` | Numeric(8, 6) | — |
| `num_trades` | Integer | — |
| `num_resolved_positions` | Integer | **NEW** |
| `profit_factor` | Numeric(28, 6) | **NEW** — gross_profit / \|gross_loss\| |
| `sharpe_ratio` | Numeric(8, 6) | **NEW** — replaces generic `risk_adj_return` |
| `max_drawdown` | Numeric(8, 6) | **NEW** — peak-to-trough decline |
| `avg_position_size` | Numeric(28, 2) | — |
| `avg_holding_duration` | Interval | — |
| `consistency_score` | Numeric(8, 6) | **NEW** — moved from ranking step |
| `experience_score` | Numeric(8, 6) | **NEW** — moved from ranking step |
| `wallet_score` | Numeric(8, 6) | — |

Why `sharpe_ratio` over `risk_adj_return`: Sharpe is the industry standard. Formula:
```
sharpe_ratio = AVG(trade_pnl) / STDDEV(trade_pnl) * SQRT(252)
```
Only computed when `num_trades >= 10`.

Index: `(snapshot_date, wallet_score DESC)`.

---

### `ranking_snapshots` (NEW — as previously agreed)

```python
class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"
    wallet           = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    snapshot_date    = Column(Date, primary_key=True)
    list_type        = Column(Text, primary_key=True)  # 'top_100' | 'emerging' | 'consistent'
    rank             = Column(Integer, nullable=False)
    wallet_score     = Column(Numeric(8, 6))
    roi              = Column(Numeric(8, 6))
    win_rate         = Column(Numeric(8, 6))
    consistency_score = Column(Numeric(8, 6))
    experience_score = Column(Numeric(8, 6))
    risk_adj_return  = Column(Numeric(8, 6))  # kept for API response compatibility

    __table_args__ = (
        Index("idx_rankings_list_date_score", "snapshot_date", "list_type", "rank"),
    )
```

---

### `position_history` (NEW — optional, append-only)

```python
class PositionHistory(Base):  # OPTIONAL
    __tablename__ = "position_history"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    wallet         = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    market_id      = Column(Text, ForeignKey("markets.id"), nullable=False)
    outcome_id     = Column(Text, ForeignKey("outcomes.id"), nullable=True)
    side           = Column(Enum("BUY", "SELL"))
    shares_before  = Column(Numeric(28, 12))
    shares_after   = Column(Numeric(28, 12))
    pnl_change     = Column(Numeric(28, 12))
    recorded_at    = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

Append-only log from the ingestion_position_sync pipeline. Every time a position changes, this table logs the delta. Enables time-travel analysis ("how did this wallet's position evolve over time?") and debugging.

Useful for Phase 2 (Niche Expertise Detection) — can analyze entry timing skill.

---

### Enums (new module: `app/models/enums.py`)

```python
from enum import StrEnum

class TradeSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"

class TradeType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class PositionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    RESOLVED = "RESOLVED"

class RankingListType(StrEnum):
    TOP_100 = "top_100"
    EMERGING = "emerging"
    CONSISTENT = "consistent"
```

---

## 3. Tables Summary

| Table | PK | FKs | Purpose |
|---|---|---|---|
| `events` | `id` | — | Polymarket event categories |
| `markets` | `id` | → `events.id` | Market metadata + volume |
| `outcomes` | `id` | → `markets.id` | Per-outcome pricing + winner |
| `wallets` | `wallet` | — | Wallet metadata + sync state |
| `trades` | `id` | → `wallets.wallet`, `markets.id`, `outcomes.id` | Trade journal |
| `positions` | `(wallet, market_id)` | → `wallets.wallet`, `markets.id`, `outcomes.id` | Current positions |
| `position_history` | `id` (auto) | → `wallets.wallet`, `markets.id` | Append-only position delta log |
| `wallet_analytics` | `(wallet, snapshot_date)` | → `wallets.wallet` | Daily analytical snapshots |
| `ranking_snapshots` | `(wallet, snapshot_date, list_type)` | → `wallets.wallet` | Materialized leaderboard lists |

---

## 4. Migration: Squash Into `001_initial.py`

Since there's no production data, replace `001_initial.py` with a single migration that creates all 9 tables. The existing `001` has `down_revision = None` — keep that. Edit in place.

```python
# alembic/versions/001_initial.py — squashed final schema

revision = "001"
down_revision = None

def upgrade():
    # 1. enum types
    op.execute("CREATE TYPE tradeside AS ENUM ('BUY', 'SELL')")
    op.execute("CREATE TYPE tradetype AS ENUM ('MARKET', 'LIMIT')")
    op.execute("CREATE TYPE positionstatus AS ENUM ('OPEN', 'CLOSED', 'RESOLVED')")

    # 2. tables …
    op.create_table("events", …)
    op.create_table("markets", …)
    op.create_table("outcomes", …)
    op.create_table("wallets", …)
    op.create_table("trades", …)
    op.create_table("positions", …)
    op.create_table("position_history", …)
    op.create_table("wallet_analytics", …)
    op.create_table("ranking_snapshots", …)

    # 3. indexes
    op.create_index("idx_markets_category", "markets", ["category"])
    op.create_index("idx_markets_created_at", "markets", ["created_at"])
    op.create_index("idx_markets_event_id", "markets", ["event_id"])
    op.create_index("idx_outcomes_market_id", "outcomes", ["market_id"])
    op.create_index("idx_wallets_is_tracked", "wallets", ["is_tracked"])
    op.create_index("idx_trades_wallet_ts", "trades", ["wallet", sa.text("timestamp DESC")])
    op.create_index("idx_positions_wallet", "positions", ["wallet"])
    op.create_index("idx_positions_market", "positions", ["market_id"])
    op.create_index("idx_wallet_analytics_date_score", "wallet_analytics",
                    ["snapshot_date", sa.text("wallet_score DESC NULLS LAST")])
    op.create_index("idx_rankings_list_date_score", "ranking_snapshots",
                    ["snapshot_date", "list_type", "rank"])

def downgrade():
    # reverse order
    for table in reversed(["ranking_snapshots", "wallet_analytics", "position_history",
                          "positions", "trades", "wallets", "outcomes", "markets", "events"]):
        op.drop_table(table)
    op.execute("DROP TYPE IF EXISTS tradeside")
    op.execute("DROP TYPE IF EXISTS tradetype")
    op.execute("DROP TYPE IF EXISTS positionstatus")
```

---

## 5. Impact on Existing Code

| File | Change Required |
|---|---|
| `app/db/models.py` | Full rewrite — 9 models, enums, FKs, composite indexes |
| `app/models/enums.py` | Already exists — update with all 4 enums |
| `app/models/schemas.py` | Add/update Pydantic models for new columns (especially `ranking_snapshots` response) |
| `app/services/leaderboard_service.py` | Update queries — read from `ranking_snapshots` instead of computing live |
| `app/services/wallet_service.py` | Update queries for new `wallet_analytics` columns |
| `app/api/v1/leaderboard.py` | May need minor column name adjustments |
| `app/api/v1/wallets.py` | May need minor column name adjustments |
| `app/tests/test_api/test_endpoints.py` | Update mock data to match new schema |
| `app/tests/conftest.py` | Update mock fixtures |
| `.opencode/plans/phase-01-etl-pipelines.md` | Update column references in all pipeline blocks |

---

## 6. Acceptance Criteria

- [ ] `alembic upgrade head` creates all 9 tables with correct columns, FKs, and indexes
- [ ] All existing tests pass (after updating mock data)
- [ ] `POST /api/v1/health` still returns `{"status": "ok"}`
- [ ] `GET /api/v1/leaderboard` returns the correct shape (even if empty)
- [ ] `GET /api/v1/wallets/{address}` returns new fields (`is_tracked`, `label`)
- [ ] `GET /api/v1/markets/{id}` returns new fields (`volume_usd`, `winning_outcome`)
- [ ] `ruff check .` and `mypy app/` pass with no new errors

---

## 7. Implementation Order

| # | Step | Est. Files Changed |
|---|---|---|
| 1 | Update `app/models/enums.py` | 1 |
| 2 | Rewrite `app/db/models.py` — all 9 models | 1 |
| 3 | Rewrite `alembic/versions/001_initial.py` | 1 |
| 4 | Update `app/models/schemas.py` | 1 |
| 5 | Update `app/services/` (leaderboard + wallet) | 2 |
| 6 | Update `app/api/v1/` (leaderboard + wallets + markets) | 3 |
| 7 | Update `app/tests/` (conftest + test_endpoints) | 2 |
| 8 | `alembic upgrade head` to verify | — |
| 9 | `pytest -v` to verify tests pass | — |
| 10 | Commit as `feat(db): redesign schema for scalability and analytics completeness` | ~12 files |

---

## 8. Decision Record

| Decision | Choice | Rationale |
|---|---|---|
| Schema change timing | **Now** (squash 001) | Zero data; cheapest time to break things |
| Numeric precision | Explicit `Numeric(p, s)` | Performance on large aggregations |
| Foreign keys | **Yes** | Data integrity worth the write overhead |
| Enums vs check constraints | **PostgreSQL enum types** | Native perf, reusable in queries |
| `position_history` | **Include** (optional) | Enables time-travel; no cost until written to |
| `winning_outcome` rename | **Yes** | Clarity — `market.outcome` was ambiguous |
| `risk_adj_return` → `sharpe_ratio` | **Yes** | Industry standard; same computation |
