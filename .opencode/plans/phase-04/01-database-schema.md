# Phase 4 — Edge Scoring — Database Schema

> **Goal**: Store per-wallet edge metrics (ROI per trade) computed from resolved markets, add `edge_score` to existing aggregation tables.
> **AI Agent Instructions**: Create the migration file `alembic/versions/008_add_edge_scoring.py`, add models to `app/db/models.py`, update Pydantic schemas in `app/models/schemas.py`, and add `edge_score` columns to `wallet_analytics` and `ranking_snapshots`.

---

## New Table: `wallet_edge_snapshots`

Stores daily edge metrics per wallet — the average, median, consistency, and volatility of edge per trade on resolved markets.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `wallet` | `text` | PK, FK → `wallets.wallet` NOT NULL | Wallet address |
| `snapshot_date` | `date` | PK NOT NULL | Date of snapshot (typically `CURRENT_DATE`) |
| `avg_edge` | `numeric(28,6)` | NOT NULL | Mean edge across all trades on resolved markets |
| `median_edge` | `numeric(28,6)` | NULLABLE | Median edge — less sensitive to outliers |
| `edge_consistency` | `numeric(8,6)` | NULLABLE | Fraction of trades with edge > 0, range [0, 1] |
| `edge_volatility` | `numeric(28,6)` | NULLABLE | Standard deviation of edge values |
| `edge_score` | `numeric(8,6)` | NULLABLE | `avg_edge` normalised to [0, 1] via min-max scaling |
| `num_edge_trades` | `integer` | NOT NULL | Total number of trades used for computation |
| `positive_edge_trades` | `integer` | NULLABLE | Count of trades where edge > 0 |
| `negative_edge_trades` | `integer` | NULLABLE | Count of trades where edge <= 0 (edge = 0 counts as negative) |
| `computed_at` | `timestamptz` | NOT NULL, default `now()` | When this snapshot was computed |

**Indexes:**

```sql
CREATE INDEX idx_ws_wallet_date ON wallet_edge_snapshots (wallet, snapshot_date DESC);
CREATE INDEX idx_ws_date ON wallet_edge_snapshots (snapshot_date DESC);
CREATE INDEX idx_ws_edge_score ON wallet_edge_snapshots (edge_score DESC);
```

---

## Modified Tables: `wallet_analytics`

Add `edge_score` column to the existing daily analytics snapshot table.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `edge_score` | `numeric(8,6)` | NULLABLE | Added in Phase 4 — edge score from `wallet_edge_snapshots` |

**No new indexes required** — the existing `wallet_analytics` indexes already cover wallet + snapshot_date queries.

---

## Modified Tables: `ranking_snapshots`

Add `edge_score` column to the ranking materialised view.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `edge_score` | `numeric(8,6)` | NULLABLE | Added in Phase 4 — used in ranking formula |

---

## Migration File (`008_add_edge_scoring.py`)

**Revision chain**: `007_add_wallet_pnl_snapshots.py` → `008_add_edge_scoring.py`

```python
"""Add wallet_edge_snapshots table and edge_score columns for Phase 4 Edge Scoring.

Revision ID: 008
Revises: 007
Create Date: 2026-06-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New table: wallet_edge_snapshots ──────────────────────────────
    op.create_table(
        "wallet_edge_snapshots",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("avg_edge", sa.Numeric(28, 6), nullable=False),
        sa.Column("median_edge", sa.Numeric(28, 6), nullable=True),
        sa.Column("edge_consistency", sa.Numeric(8, 6), nullable=True),
        sa.Column("edge_volatility", sa.Numeric(28, 6), nullable=True),
        sa.Column("edge_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("num_edge_trades", sa.Integer(), nullable=False),
        sa.Column("positive_edge_trades", sa.Integer(), nullable=True),
        sa.Column("negative_edge_trades", sa.Integer(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["wallet"], ["wallets.wallet"], name="fk_ws_wallet"
        ),
        sa.PrimaryKeyConstraint("wallet", "snapshot_date"),
    )
    op.create_index(
        "idx_ws_wallet_date",
        "wallet_edge_snapshots",
        [sa.text("wallet DESC"), sa.text("snapshot_date DESC")],
    )
    op.create_index(
        "idx_ws_date",
        "wallet_edge_snapshots",
        [sa.text("snapshot_date DESC")],
    )
    op.create_index(
        "idx_ws_edge_score",
        "wallet_edge_snapshots",
        [sa.text("edge_score DESC")],
    )

    # ── Add edge_score to existing tables ─────────────────────────────
    op.add_column(
        "wallet_analytics",
        sa.Column("edge_score", sa.Numeric(8, 6), nullable=True),
    )
    op.add_column(
        "ranking_snapshots",
        sa.Column("edge_score", sa.Numeric(8, 6), nullable=True),
    )


def downgrade() -> None:
    # ── Drop edge_score columns first ─────────────────────────────────
    op.drop_column("ranking_snapshots", "edge_score")
    op.drop_column("wallet_analytics", "edge_score")

    # ── Drop wallet_edge_snapshots table ──────────────────────────────
    op.drop_index("idx_ws_edge_score", table_name="wallet_edge_snapshots")
    op.drop_index("idx_ws_date", table_name="wallet_edge_snapshots")
    op.drop_index("idx_ws_wallet_date", table_name="wallet_edge_snapshots")
    op.drop_table("wallet_edge_snapshots")
```

---

## SQLAlchemy Models

Add to `app/db/models.py` — insert after the `WalletPnlSnapshot` class (before the file ends):

```python
class WalletEdgeSnapshot(Base):
    __tablename__ = "wallet_edge_snapshots"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    avg_edge = Column(Numeric(28, 6), nullable=False)
    median_edge = Column(Numeric(28, 6), nullable=True)
    edge_consistency = Column(Numeric(8, 6), nullable=True)
    edge_volatility = Column(Numeric(28, 6), nullable=True)
    edge_score = Column(Numeric(8, 6), nullable=True)
    num_edge_trades = Column(Integer, nullable=False)
    positive_edge_trades = Column(Integer, nullable=True)
    negative_edge_trades = Column(Integer, nullable=True)
    computed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

### Add `edge_score` to `WalletAnalytic` model

Find the `WalletAnalytic` class and add after its existing columns:

```python
class WalletAnalytic(Base):
    __tablename__ = "wallet_analytics"
    # ... existing columns ...
    edge_score = Column(Numeric(8, 6), nullable=True)  # Phase 4
```

### Add `edge_score` to `RankingSnapshot` model

Find the `RankingSnapshot` class and add after its existing columns:

```python
class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"
    # ... existing columns ...
    edge_score = Column(Numeric(8, 6), nullable=True)  # Phase 4
```

---

## Pydantic Schemas

Add to `app/models/schemas.py` — insert after the `AlertListResponse` class (or at the end):

```python
class WalletEdgeSnapshot(BaseModel):
    wallet: str
    snapshot_date: date
    avg_edge: Decimal
    median_edge: Optional[Decimal] = None
    edge_consistency: Optional[Decimal] = None
    edge_volatility: Optional[Decimal] = None
    edge_score: Optional[Decimal] = None
    num_edge_trades: int
    positive_edge_trades: Optional[int] = None
    negative_edge_trades: Optional[int] = None
    computed_at: datetime

    model_config = {"from_attributes": True}


class EdgeLeaderboardEntry(BaseModel):
    wallet: str
    edge_score: Decimal
    avg_edge: Decimal
    edge_consistency: Optional[Decimal] = None
    num_edge_trades: int
    rank: int


class EdgeLeaderboardResponse(BaseModel):
    data: list[EdgeLeaderboardEntry]
    limit: int
    offset: int
```

### Update `LeaderboardEntry` schema

Add `edge_score` and `edge_consistency` fields to the existing `LeaderboardEntry`:

```python
class LeaderboardEntry(BaseModel):
    # ... existing fields ...
    edge_score: Optional[Decimal] = None       # Phase 4
    edge_consistency: Optional[Decimal] = None  # Phase 4
```

### Update `WalletDetail` schema

Add `edge_metrics` to the wallet detail response:

```python
class WalletDetail(BaseModel):
    # ... existing fields ...
    edge_metrics: Optional[WalletEdgeSnapshot] = None  # Phase 4
```

---

## Update `app/models/schemas.py` imports

Ensure all required imports exist:

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
```

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `alembic/versions/008_add_edge_scoring.py` |
| EDIT | `app/db/models.py` — add `WalletEdgeSnapshot` class; add `edge_score` to `WalletAnalytic` and `RankingSnapshot` |
| EDIT | `app/models/schemas.py` — add `WalletEdgeSnapshot`, `EdgeLeaderboardEntry`, `EdgeLeaderboardResponse`; update `LeaderboardEntry` and `WalletDetail` |
| RUN | `alembic upgrade head` |

---

## Verification

```bash
alembic upgrade head            # should apply 008
alembic downgrade -1            # should drop edge_score columns + wallet_edge_snapshots
alembic upgrade head            # re-apply, no errors
psql -U app -d polymarket -c "\d wallet_edge_snapshots"  # verify columns
psql -U app -d polymarket -c "\d wallet_analytics"       # verify edge_score column exists
psql -U app -d polymarket -c "\d ranking_snapshots"      # verify edge_score column exists
```
