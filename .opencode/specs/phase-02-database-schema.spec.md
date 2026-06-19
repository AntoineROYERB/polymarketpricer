# Phase 2 — Database Schema: Per-Category Wallet Analytics

> **Spec Status**: Final  
> **Target Release**: v0.2.0  
> **Plan Reference**: `.opencode/plans/phase-02-database-schema.md`  
> **Author**: Platform Team  
> **Last Updated**: 2026-06-17

---

## Table of Contents

1. [Overview](#1-overview)
2. [New Tables](#2-new-tables)
3. [Migration: `002_category_analytics.py`](#3-migration-002_category_analyticspy)
4. [SQLAlchemy Models](#4-sqlalchemy-models)
5. [Pydantic Schemas](#5-pydantic-schemas)
6. [Impact Analysis](#6-impact-analysis)
7. [Verification Steps](#7-verification-steps)
8. [Rollback Plan](#8-rollback-plan)

---

## 1. Overview

Phase 2 introduces two new database tables that extend the existing analytics pipeline with per-category breakdowns. The existing `wallet_analytics` and `ranking_snapshots` tables provide wallet-level aggregates across all markets. The new tables decompose those aggregates by `MarketCategory` (8 categories: Politics, Crypto, Sports, Economics, Technology, AI, Geopolitics, Entertainment).

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Separate tables** (not JSONB columns on existing tables) | Enables indexed leaderboard queries per category without impacting Phase 1 query performance |
| **Composite PKs** mirror existing patterns | Consistent with `wallet_analytics` (wallet + snapshot_date) and `ranking_snapshots` (wallet + snapshot_date + list_type) |
| **`category` is plain Text** (not an enum FK) | Matches existing `markets.category` and `events.category` columns; avoids coupling schemas to the enum definition in `app/models/enums.py` |
| **`is_specialist` boolean** | Computed column: `true` when a wallet has > N trades, > M volume, and above-median ROI within a category. Set during the analytics computation ETL step. |

---

## 2. New Tables

### 2.1 `category_analytics`

Per-wallet, per-category, per-day analytical snapshot. One row per (wallet, category, snapshot_date) tuple.

**Columns:**

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `wallet` | `Text` | `PK`, `FK → wallets.wallet` | Wallet address |
| `category` | `Text` | `PK` | One of the 8 `MarketCategory` values |
| `snapshot_date` | `Date` | `PK` | Date of the snapshot |
| `num_trades` | `Integer` | nullable | Count of trades in this category |
| `total_volume` | `Numeric(28, 2)` | nullable | Sum of \|amount_usd\| for trades in category |
| `total_cost_basis` | `Numeric(28, 2)` | nullable | Sum of cost basis for category positions |
| `total_pnl` | `Numeric(28, 2)` | nullable | Realized + unrealized PnL in category |
| `total_realized_pnl` | `Numeric(28, 2)` | nullable | Realized PnL only |
| `total_unrealized_pnl` | `Numeric(28, 2)` | nullable | Unrealized PnL only |
| `roi` | `Numeric(8, 6)` | nullable | ROI = total_pnl / total_cost_basis (decimal ratio, not percentage × 100) |
| `win_rate` | `Numeric(8, 6)` | nullable | Wins ÷ resolved positions in category, range [0, 1] |
| `num_resolved_positions` | `Integer` | nullable | Count of resolved positions |
| `profit_factor` | `Numeric(28, 6)` | nullable | Gross profit ÷ \|gross loss\|, always ≥ 0 |
| `avg_position_size` | `Numeric(28, 2)` | nullable | Average position size in category |
| `avg_holding_duration` | `Interval` | nullable | Average holding time per position |
| `is_specialist` | `Boolean` | not null, default `false` | True if expertise criteria met |
| `category_rank` | `Integer` | nullable | Rank within category (populated during ranking computation) |

**Indexes:**

| Index Name | Columns | Purpose |
|---|---|---|
| `idx_cat_analytics_leaderboard` | `(snapshot_date, category, category_rank)` | Fast leaderboard queries: top N wallets per category per day |
| `idx_cat_analytics_wallet_date` | `(wallet, snapshot_date)` | Fast wallet profile queries: all categories for a wallet on a date |

**SQL (DDL reference):**

```sql
CREATE TABLE category_analytics (
    wallet              TEXT           NOT NULL,
    category            TEXT           NOT NULL,
    snapshot_date       DATE           NOT NULL,
    num_trades          INTEGER,
    total_volume        NUMERIC(28, 2),
    total_cost_basis    NUMERIC(28, 2),
    total_pnl           NUMERIC(28, 2),
    total_realized_pnl  NUMERIC(28, 2),
    total_unrealized_pnl NUMERIC(28, 2),
    roi                 NUMERIC(8, 6),
    win_rate            NUMERIC(8, 6),
    num_resolved_positions INTEGER,
    profit_factor       NUMERIC(28, 6),
    avg_position_size   NUMERIC(28, 2),
    avg_holding_duration INTERVAL,
    is_specialist       BOOLEAN       NOT NULL DEFAULT FALSE,
    category_rank       INTEGER,

    PRIMARY KEY (wallet, category, snapshot_date),
    FOREIGN KEY (wallet) REFERENCES wallets(wallet)
);

CREATE INDEX idx_cat_analytics_leaderboard
    ON category_analytics (snapshot_date, category, category_rank);

CREATE INDEX idx_cat_analytics_wallet_date
    ON category_analytics (wallet, snapshot_date);
```

### 2.2 `category_rankings`

Materialized leaderboard lists per category (analogous to `ranking_snapshots` for the global leaderboard).

**Columns:**

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `wallet` | `Text` | `PK`, `FK → wallets.wallet` | Wallet address |
| `category` | `Text` | `PK` | One of the 8 `MarketCategory` values |
| `snapshot_date` | `Date` | `PK` | Date of the snapshot |
| `list_type` | `Text` | `PK` | `top_50` or `specialists` |
| `rank` | `Integer` | not null | Ordinal rank within the list |
| `wallet_score` | `Numeric(8, 6)` | nullable | Overall wallet score from Phase 1 |
| `roi` | `Numeric(8, 6)` | nullable | Category ROI |
| `win_rate` | `Numeric(8, 6)` | nullable | Category win rate |
| `total_pnl` | `Numeric(28, 2)` | nullable | Category PnL |
| `num_trades` | `Integer` | nullable | Category trade count |
| `total_volume` | `Numeric(28, 2)` | nullable | Category volume |

**Indexes:**

| Index Name | Columns | Purpose |
|---|---|---|
| `idx_cat_rankings_list` | `(snapshot_date, category, list_type, rank)` | Fast leaderboard queries |

**SQL (DDL reference):**

```sql
CREATE TABLE category_rankings (
    wallet          TEXT           NOT NULL,
    category        TEXT           NOT NULL,
    snapshot_date   DATE           NOT NULL,
    list_type       TEXT           NOT NULL,
    rank            INTEGER        NOT NULL,
    wallet_score    NUMERIC(8, 6),
    roi             NUMERIC(8, 6),
    win_rate        NUMERIC(8, 6),
    total_pnl       NUMERIC(28, 2),
    num_trades      INTEGER,
    total_volume    NUMERIC(28, 2),

    PRIMARY KEY (wallet, category, snapshot_date, list_type),
    FOREIGN KEY (wallet) REFERENCES wallets(wallet)
);

CREATE INDEX idx_cat_rankings_list
    ON category_rankings (snapshot_date, category, list_type, rank);
```

---

## 3. Migration: `002_category_analytics.py`

### 3.1 File Location

`alembic/versions/002_category_analytics.py`

### 3.2 Revision Chain

```python
revision = "002"
down_revision = "001"
```

### 3.3 Full Migration Code

```python
"""Add category_analytics and category_rankings tables for per-category analytics.

Revision ID: 002
Revises: 001
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── category_analytics ──────────────────────────────────────────
    op.create_table(
        "category_analytics",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column("total_volume", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_cost_basis", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_realized_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_unrealized_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("roi", sa.Numeric(8, 6), nullable=True),
        sa.Column("win_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("num_resolved_positions", sa.Integer(), nullable=True),
        sa.Column("profit_factor", sa.Numeric(28, 6), nullable=True),
        sa.Column("avg_position_size", sa.Numeric(28, 2), nullable=True),
        sa.Column("avg_holding_duration", sa.Interval(), nullable=True),
        sa.Column(
            "is_specialist",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("category_rank", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["wallet"],
            ["wallets.wallet"],
            name="fk_cat_analytics_wallet",
        ),
        sa.PrimaryKeyConstraint("wallet", "category", "snapshot_date"),
    )
    op.create_index(
        "idx_cat_analytics_leaderboard",
        "category_analytics",
        ["snapshot_date", "category", "category_rank"],
    )
    op.create_index(
        "idx_cat_analytics_wallet_date",
        "category_analytics",
        ["wallet", "snapshot_date"],
    )

    # ── category_rankings ───────────────────────────────────────────
    op.create_table(
        "category_rankings",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("list_type", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("wallet_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("roi", sa.Numeric(8, 6), nullable=True),
        sa.Column("win_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("total_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column("total_volume", sa.Numeric(28, 2), nullable=True),
        sa.ForeignKeyConstraint(
            ["wallet"],
            ["wallets.wallet"],
            name="fk_cat_rankings_wallet",
        ),
        sa.PrimaryKeyConstraint("wallet", "category", "snapshot_date", "list_type"),
    )
    op.create_index(
        "idx_cat_rankings_list",
        "category_rankings",
        ["snapshot_date", "category", "list_type", "rank"],
    )


def downgrade() -> None:
    op.drop_table("category_rankings")
    op.drop_table("category_analytics")
```

### 3.4 Migration Notes

- **No new ENUM types** are created. The `category` column uses plain `sa.Text()`, consistent with `markets.category` and `events.category`.
- **Explicit FK constraint names** (`fk_cat_analytics_wallet`, `fk_cat_rankings_wallet`) are used for clean downgrades and error messages. The existing Phase 1 migration uses unnamed constraints (PostgreSQL auto-names them); we optionally name them here for explicitness.
- **`server_default=sa.false()`** matches the pattern used for `events.closed` and `wallets.is_tracked` in the Phase 1 migration.
- **Downgrade** drops `category_rankings` first (child-conceptually, though neither table references the other), then `category_analytics`. No ENUM types need dropping.

---

## 4. SQLAlchemy Models

### 4.1 File Location

Additions to `app/db/models.py` (append after `class RankingSnapshot`).

### 4.2 New Models

```python
class CategoryAnalytic(Base):
    __tablename__ = "category_analytics"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    category = Column(Text, primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    num_trades = Column(Integer, nullable=True)
    total_volume = Column(Numeric(28, 2), nullable=True)
    total_cost_basis = Column(Numeric(28, 2), nullable=True)
    total_pnl = Column(Numeric(28, 2), nullable=True)
    total_realized_pnl = Column(Numeric(28, 2), nullable=True)
    total_unrealized_pnl = Column(Numeric(28, 2), nullable=True)
    roi = Column(Numeric(8, 6), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    num_resolved_positions = Column(Integer, nullable=True)
    profit_factor = Column(Numeric(28, 6), nullable=True)
    avg_position_size = Column(Numeric(28, 2), nullable=True)
    avg_holding_duration = Column(Interval, nullable=True)
    is_specialist = Column(Boolean, nullable=False, default=False)
    category_rank = Column(Integer, nullable=True)

    # relationships
    wallet_rel = relationship("Wallet", backref="category_analytics")

    __table_args__ = (
        Index(
            "idx_cat_analytics_leaderboard",
            "snapshot_date",
            "category",
            "category_rank",
        ),
        Index(
            "idx_cat_analytics_wallet_date",
            "wallet",
            "snapshot_date",
        ),
    )


class CategoryRanking(Base):
    __tablename__ = "category_rankings"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    category = Column(Text, primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    list_type = Column(Text, primary_key=True)
    rank = Column(Integer, nullable=False)
    wallet_score = Column(Numeric(8, 6), nullable=True)
    roi = Column(Numeric(8, 6), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    total_pnl = Column(Numeric(28, 2), nullable=True)
    num_trades = Column(Integer, nullable=True)
    total_volume = Column(Numeric(28, 2), nullable=True)

    # relationships
    wallet_rel = relationship("Wallet", backref="category_rankings")

    __table_args__ = (
        Index(
            "idx_cat_rankings_list",
            "snapshot_date",
            "category",
            "list_type",
            "rank",
        ),
    )
```

### 4.3 Required Imports (already present in Phase 1)

These columns are already imported in `models.py`:

```python
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey,
    Index, Integer, Interval, Numeric, Text, func, text,
)
from sqlalchemy.orm import DeclarativeBase, relationship
```

No new imports are needed for the new models — all required types (`Text`, `Date`, `Integer`, `Numeric`, `Interval`, `Boolean`, `ForeignKey`, `Index`, `relationship`) are already imported.

### 4.4 Model Design Notes

- **`wallet_rel` relationship**: Uses `backref` (not `back_populates`) for simplicity, since the `Wallet` model does not need explicit `category_analytics` or `category_rankings` attributes. If `Wallet` needs these collections later, migrate to `back_populates`.
- **Composite PKs** match the table DDL exactly: `(wallet, category, snapshot_date)` for `CategoryAnalytic` and `(wallet, category, snapshot_date, list_type)` for `CategoryRanking`.
- **`default=False`** on `is_specialist` uses SQLAlchemy-side default (not server default). The migration's `server_default=sa.false()` handles the database-level default. Both are set for consistency.

---

## 5. Pydantic Schemas

### 5.1 File Location

Additions to `app/models/schemas.py` (append at end of file).

### 5.2 New Schemas

```python
class CategoryAnalyticsData(BaseModel):
    """Per-category analytics summary for a wallet."""
    category: str
    num_trades: Optional[int] = None
    total_volume: Optional[Decimal] = None
    total_cost_basis: Optional[Decimal] = None
    total_pnl: Optional[Decimal] = None
    total_realized_pnl: Optional[Decimal] = None
    total_unrealized_pnl: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    num_resolved_positions: Optional[int] = None
    profit_factor: Optional[Decimal] = None
    avg_position_size: Optional[Decimal] = None
    avg_holding_duration: Optional[str] = None
    is_specialist: bool = False
    category_rank: Optional[int] = None

    model_config = {"from_attributes": True}


class WalletCategorySummary(BaseModel):
    """Wallet identity + per-category breakdown."""
    wallet: str
    categories: list[CategoryAnalyticsData] = []

    model_config = {"from_attributes": True}


class WalletCategoryResponse(BaseModel):
    """Response wrapper for a wallet's per-category analytics."""
    data: WalletCategorySummary


class CategoryLeaderboardEntry(BaseModel):
    """One row in a category leaderboard."""
    rank: int
    wallet: str
    wallet_score: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    total_pnl: Optional[Decimal] = None
    num_trades: Optional[int] = None
    total_volume: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class CategoryLeaderboardResponse(BaseModel):
    """Response wrapper for a category leaderboard."""
    category: str
    list_type: str
    data: list[CategoryLeaderboardEntry]
    limit: int
    offset: int


class CategoryDetailResponse(BaseModel):
    """Aggregated overview of all categories."""
    categories: list[str]
    total_wallets_tracked: int
    snapshot_date: date

    model_config = {"from_attributes": True}
```

### 5.3 Required Imports (already present in Phase 1)

The existing imports in `schemas.py` are:

```python
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
```

Add `from datetime import date` to the existing import line:

```python
from datetime import date, datetime
```

### 5.4 Schema Design Notes

- **`CategoryAnalyticsData`** mirrors the `CategoryAnalytic` model columns as camelCase-like field names (matching the existing `WalletAnalyticsData` pattern). `avg_holding_duration` is `Optional[str]` (serialized from `Interval` as an ISO 8601 duration string) rather than `Optional[Decimal]`, matching the existing `WalletAnalyticsData` convention.
- **`WalletCategorySummary` + `WalletCategoryResponse`**: Used by the wallet profile endpoint to return all category breakdowns for a given wallet.
- **`CategoryLeaderboardEntry` + `CategoryLeaderboardResponse`**: Used by the leaderboard endpoint to return ranked wallets within a category. The `list_type` field distinguishes `top_50` from `specialists`.
- **`CategoryDetailResponse`**: Used by a category overview endpoint to list available categories and aggregate stats.

---

## 6. Impact Analysis

### 6.1 Files That Change

| # | File | Change Type | Description |
|---|---|---|---|
| 1 | `alembic/versions/002_category_analytics.py` | **CREATE** | New migration file (full code in §3.3) |
| 2 | `app/db/models.py` | **MODIFY** | Append `CategoryAnalytic` and `CategoryRanking` model classes (full code in §4.2) |
| 3 | `app/models/schemas.py` | **MODIFY** | Append new Pydantic schemas from §5.2; add `date` to imports from `datetime` |
| 4 | `app/tests/test_db_integrity.py` | **MODIFY** | Add integration tests for the new tables (see §7.2) |
| 5 | `docker/initdb/seed.sql` | **REFRESH** | After migration is applied and pipelines run, regenerate seed dump to include new table data |

### 6.2 Files That Do NOT Change

| File | Reason |
|---|---|
| `app/models/enums.py` | `MarketCategory` already exists; `category` column uses plain Text |
| `alembic/env.py` | No config change — it auto-discovers new models via `Base.metadata` |
| `app/db/__init__.py` | Empty file, no initialization needed |
| `docker-compose.yml` | No new services or volume mounts |
| `Dockerfile` / `requirements.txt` | No new Python dependencies |
| `app/api/` routes | Will be added in a separate Phase 2 API spec (out of scope for this schema spec) |
| `magic/` pipeline files | Will be updated in a separate Phase 2 ETL spec (out of scope for this schema spec) |

### 6.3 No Breaking Changes to Phase 1

- All existing tables keep their schemas unchanged.
- All existing FKs remain valid.
- The new migration appends to the chain; no squash or rebase is required.
- Existing `WalletAnalytic` and `RankingSnapshot` models continue to function.
- All existing API endpoints continue to return the same data.
- All existing integration tests (32 tests, `test_db_integrity.py`) remain valid and should still pass.

---

## 7. Verification Steps

### 7.1 Migration Tests

```bash
# 1. Up migration
alembic upgrade head

# 2. Verify tables exist
psql -U app -d polymarket -c "\dt category_*"

# 3. Verify columns and types
psql -U app -d polymarket -c "\d category_analytics"
psql -U app -d polymarket -c "\d category_rankings"

# 4. Verify indexes
psql -U app -d polymarket -c "\di idx_cat_*"

# 5. Verify FKs
psql -U app -d polymarket -c """
    SELECT conname, conrelid::regclass AS table_name
    FROM pg_constraint
    WHERE confrelid = 'wallets'::regclass
      AND conname LIKE 'fk_cat_%';
"""

# 6. Down migration
alembic downgrade -1

# 7. Verify tables dropped
psql -U app -d polymarket -c "\dt category_*"
# → Should return "Did not find any relations."

# 8. Re-up for production state
alembic upgrade head
```

### 7.2 Integration Tests (add to `test_db_integrity.py`)

Add these new parametrized and standalone tests to the existing test file:

```python
# ── Category analytics integration tests ─────────────────────────

CATEGORY_ROW_THRESHOLDS = {
    "category_analytics": 10,
    "category_rankings": 10,
}

CATEGORY_EMPTY_TABLES: set[str] = set()  # both should have data if ETL ran

CATEGORY_FK_CHECKS = [
    ("category_analytics", "wallets", "wallet", "wallet"),
    ("category_rankings", "wallets", "wallet", "wallet"),
]

CATEGORY_NOT_NULL_CHECKS = [
    ("category_analytics", "wallet"),
    ("category_analytics", "category"),
    ("category_analytics", "snapshot_date"),
    ("category_analytics", "is_specialist"),
    ("category_rankings", "wallet"),
    ("category_rankings", "category"),
    ("category_rankings", "snapshot_date"),
    ("category_rankings", "list_type"),
    ("category_rankings", "rank"),
]


@pytest.mark.parametrize("tbl,min_rows", list(CATEGORY_ROW_THRESHOLDS.items()))
def test_category_table_row_counts(conn: Connection, tbl: str, min_rows: int) -> None:
    count: int = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
    assert count >= min_rows, f"{tbl} has {count} rows, expected at least {min_rows}"


@pytest.mark.parametrize(
    ("child_tbl", "parent_tbl", "child_col", "parent_col"),
    CATEGORY_FK_CHECKS,
    ids=[f"{c}.{cc} -> {p}.{pc}" for c, p, cc, pc in CATEGORY_FK_CHECKS],
)
def test_category_referential_integrity(
    conn: Connection,
    child_tbl: str,
    parent_tbl: str,
    child_col: str,
    parent_col: str,
) -> None:
    count = conn.execute(
        text(
            f"SELECT count(*) FROM {child_tbl} c "
            f"LEFT JOIN {parent_tbl} p ON c.{child_col} = p.{parent_col} "
            f"WHERE p.{parent_col} IS NULL"
        )
    ).scalar()
    assert count == 0, (
        f"{count} rows in {child_tbl}.{child_col} without matching "
        f"{parent_tbl}.{parent_col}"
    )


@pytest.mark.parametrize(
    "tbl,col",
    CATEGORY_NOT_NULL_CHECKS,
    ids=[f"{t}.{c}" for t, c in CATEGORY_NOT_NULL_CHECKS],
)
def test_category_not_null_columns(conn: Connection, tbl: str, col: str) -> None:
    count: int = conn.execute(
        text(f"SELECT count(*) FROM {tbl} WHERE {col} IS NULL")
    ).scalar() or 0
    assert count == 0, f"{tbl}.{col} has {count} NULL values"


def test_category_analytics_categories_are_valid(conn: Connection) -> None:
    """Ensure category column contains only known MarketCategory values."""
    valid = {
        "Politics", "Crypto", "Sports", "Economics",
        "Technology", "AI", "Geopolitics", "Entertainment",
    }
    result = conn.execute(
        text("SELECT DISTINCT category FROM category_analytics")
    ).scalars().all()
    for cat in result:
        assert cat in valid, f"Unexpected category: {cat}"


def test_category_rankings_list_types_are_valid(conn: Connection) -> None:
    """Ensure list_type column contains only known list type values."""
    valid = {"top_50", "specialists"}
    result = conn.execute(
        text("SELECT DISTINCT list_type FROM category_rankings")
    ).scalars().all()
    for lt in result:
        assert lt in valid, f"Unexpected list_type: {lt}"


def test_category_rankings_rank_is_sequential(conn: Connection) -> None:
    """Check ranks within each (snapshot_date, category, list_type) group start at 1."""
    result = conn.execute(
        text(
            "SELECT snapshot_date, category, list_type, MIN(rank), MAX(rank), COUNT(*)"
            " FROM category_rankings"
            " GROUP BY snapshot_date, category, list_type"
        )
    ).fetchall()
    for row in result:
        assert row[3] == 1, (
            f"Ranks for {row[0]} / {row[1]} / {row[2]} start at {row[3]}, expected 1"
        )
        assert row[4] == row[5], (
            f"Ranks for {row[0]} / {row[1]} / {row[2]} have gaps: "
            f"max={row[4]}, count={row[5]}"
        )


def test_category_analytics_snapshot_date_is_today(conn: Connection) -> None:
    today = date.today()
    dates = conn.execute(
        text("SELECT DISTINCT snapshot_date FROM category_analytics")
    ).scalars().all()
    for d in dates:
        assert d == today, f"Found stale snapshot_date {d}, expected {today}"
```

**Integration test summary:** The new tests (10 total) cover:

| Test | What it validates |
|---|---|
| `test_category_table_row_counts` | 2 parametrized — minimum row thresholds for both tables |
| `test_category_referential_integrity` | 2 parametrized — no orphaned FKs to `wallets` |
| `test_category_not_null_columns` | 9 parametrized — critical columns not null |
| `test_category_analytics_categories_are_valid` | Category values match `MarketCategory` enum |
| `test_category_rankings_list_types_are_valid` | List types match expected values |
| `test_category_rankings_rank_is_sequential` | Ranks are 1-indexed and gap-free |
| `test_category_analytics_snapshot_date_is_today` | No stale data |

Total Phase 1 + Phase 2 integration tests: **32 + 16 = 48**.

### 7.3 Model Import Test

```bash
# Verify new models can be imported
python3 -c "
from app.db.models import CategoryAnalytic, CategoryRanking, Base
print('CategoryAnalytic table:', CategoryAnalytic.__tablename__)
print('CategoryRanking table:', CategoryRanking.__tablename__)
print('Tables in metadata:', [t.name for t in Base.metadata.tables.values()])
"
```

Expected output:
```
CategoryAnalytic table: category_analytics
CategoryRanking table: category_rankings
Tables in metadata: ['events', 'markets', 'outcomes', 'wallets', ...,
                     'category_analytics', 'category_rankings']
```

### 7.4 Schema Import Test

```bash
python3 -c "
from app.models.schemas import (
    CategoryAnalyticsData, WalletCategorySummary, WalletCategoryResponse,
    CategoryLeaderboardEntry, CategoryLeaderboardResponse,
    CategoryDetailResponse,
)
print('All schemas import successfully')
"
```

### 7.5 Alembic History Check

```bash
alembic history
# Expected:
# 002 -> 001 (head), 002_category_analytics
# 001 -> (base), 001_initial
```

### 7.6 Full Test Suite

```bash
# Unit/API tests (mock-based)
python3 -m pytest app/tests/test_api/ -v

# Integration tests (requires running database)
python3 -m pytest app/tests/ -v -m integration
```

---

## 8. Rollback Plan

### 8.1 Standard Rollback

```bash
# Revert the migration
alembic downgrade -1

# Verify
alembic current
# → Should show "001" (or "001_initial")
```

### 8.2 What the Downgrade Does

1. Drops `category_rankings` table (and its indexes).
2. Drops `category_analytics` table (and its indexes).
3. No ENUM types to clean up (none were created).
4. No data loss in Phase 1 tables.

### 8.3 Rollback Safety

- The downgrade is idempotent (tables are `DROP TABLE` with no `IF EXISTS`, but Alembic only runs the downgrade if the migration was applied).
- Phase 1 seed data is unaffected.
- If rollback is done after ETL pipelines have written data to the new tables, that data is lost. This is acceptable for Phase 2 since the ETL pipelines can recompute it.

---

## Appendix A: Type Mapping Reference

All numeric type mappings follow the existing Phase 1 conventions:

| Usage | SQLAlchemy / Alembic Type | SQL Type | Precision |
|---|---|---|---|
| Monetary amounts (PnL, volume, cost basis) | `Numeric(28, 2)` | `NUMERIC(28,2)` | 28 digits, 2 decimal places |
| Prices, shares, trade amounts | `Numeric(28, 12)` | `NUMERIC(28,12)` | 28 digits, 12 decimal places |
| Ratios (ROI, win rate, scores) | `Numeric(8, 6)` | `NUMERIC(8,6)` | 8 digits, 6 decimal places |
| Profit factor | `Numeric(28, 6)` | `NUMERIC(28,6)` | 28 digits, 6 decimal places |
| Time durations | `Interval` | `INTERVAL` | PostgreSQL interval type |
| Dates | `Date` | `DATE` | No time component |
| Timestamps | `DateTime(timezone=True)` | `TIMESTAMP WITH TIME ZONE` | With timezone |
| Text identifiers | `Text` | `TEXT` | Unlimited length |
| Counters | `Integer` | `INTEGER` | 4-byte integer |
| Booleans | `Boolean` | `BOOLEAN` | True/False |

## Appendix B: Dependency Graph

```
wallets (Phase 1)
    ├── wallet_analytics (Phase 1)  — aggregate across all categories
    ├── ranking_snapshots (Phase 1) — aggregate leaderboard
    ├── category_analytics (Phase 2)  — per-category breakdown  ← NEW
    └── category_rankings (Phase 2)   — per-category leaderboard ← NEW

markets (Phase 1)
    └── category column (Text) — joins to category_analytics.category logically (no FK)
```

No circular dependencies. New tables only reference `wallets` via FK. The `category` column is a logical/application-level join key to `markets.category`, enforced by application logic rather than a database FK constraint (consistent with Phase 1 design).
