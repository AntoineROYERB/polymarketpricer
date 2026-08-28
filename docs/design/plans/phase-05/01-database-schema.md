# Phase 5 — Follow & Paper Trading — Database Schema

> **Goal**: Add tables for wallet following and paper trading simulation, plus `follow_score` on `wallet_analytics`.
> **AI Agent Instructions**: Create 3 migration files (`018_add_wallet_follows.py`, `019_add_paper_trading.py`, `020_add_follow_score.py`), add models to `app/db/models.py`, and add Pydantic schemas to `app/models/schemas.py`.

---

## New Table: `wallet_follows`

Tracks which wallets the user follows and the copy configuration.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | |
| `wallet` | `text` | FK → `wallets.wallet` NOT NULL | Wallet being followed |
| `user_id` | `text` | NOT NULL | Placeholder for future auth (use `'default'` for now) |
| `label` | `text` | NULLABLE | Custom label (e.g. "Crypto whale") |
| `active` | `boolean` | NOT NULL, default `true` | Soft delete flag |
| `auto_copy_enabled` | `boolean` | NOT NULL, default `false` | Auto-copy trades |
| `copy_mode` | `text` | NULLABLE, check in (`'proportional'`, `'fixed'`) | Sizing strategy |
| `copy_value` | `numeric(28,6)` | NOT NULL, default `0.05` | 5% proportion or $X amount |
| `category_filter` | `jsonb` | NULLABLE | Array of categories, e.g. `["Politics","Crypto"]`. `NULL` = all |
| `followed_at` | `timestamptz` | NOT NULL, default `now()` | |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | |
| `unfollowed_at` | `timestamptz` | NULLABLE | Set on unfollow |

**Unique constraint:** `(user_id, wallet)` — can't follow same wallet twice.

**Indexes:**
```sql
CREATE INDEX idx_follows_user_active ON wallet_follows (user_id, active) WHERE active = true;
CREATE INDEX idx_follows_wallet ON wallet_follows (wallet);
CREATE INDEX idx_follows_auto_copy ON wallet_follows (auto_copy_enabled) WHERE auto_copy_enabled = true;
```

---

## New Table: `paper_portfolios`

One portfolio per user (single-user mode for now).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | |
| `user_id` | `text` | NOT NULL | Placeholder for future auth |
| `name` | `text` | NOT NULL, default `'Main'` | Portfolio label |
| `initial_balance` | `numeric(28,2)` | NOT NULL | Starting virtual capital |
| `current_balance` | `numeric(28,2)` | NOT NULL | Available cash |
| `total_realized_pnl` | `numeric(28,2)` | NOT NULL, default `0` | Sum of all closed trade PnLs |
| `total_unrealized_pnl` | `numeric(28,2)` | NOT NULL, default `0` | Current open positions PnL |
| `total_pnl` | `numeric(28,2)` | NOT NULL, default `0` | realized + unrealized |
| `total_roi` | `numeric(28,6)` | NULLABLE | (total_pnl / initial_balance) * 100 |
| `total_trades` | `integer` | NOT NULL, default `0` | |
| `total_volume` | `numeric(28,2)` | NOT NULL, default `0` | |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | |

**Indexes:**
```sql
CREATE INDEX idx_portfolios_user ON paper_portfolios (user_id);
```

---

## New Table: `paper_positions`

Tracks current open (and historical closed) simulated positions.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | |
| `portfolio_id` | `uuid` | FK → `paper_portfolios.id` NOT NULL | |
| `market_id` | `text` | FK → `markets.id` NOT NULL | |
| `outcome` | `text` | NOT NULL | e.g. "Yes" |
| `side` | `text` | NOT NULL, check in (`'BUY'`, `'SELL'`) | |
| `status` | `text` | NOT NULL, default `'OPEN'`, check in (`'OPEN'`, `'CLOSED'`, `'RESOLVED'`) | |
| `shares` | `numeric(28,12)` | NOT NULL | Current shares held |
| `avg_entry_price` | `numeric(28,12)` | NOT NULL | Weighted average entry |
| `current_price` | `numeric(28,12)` | NULLABLE | Last known market price |
| `cost_basis` | `numeric(28,2)` | NOT NULL | Total amount spent |
| `realized_pnl` | `numeric(28,2)` | NOT NULL, default `0` | For partially closed positions |
| `unrealized_pnl` | `numeric(28,2)` | NULLABLE | (current_price - avg_entry) * shares |
| `followed_wallet` | `text` | FK → `wallets.wallet` NOT NULL | Source wallet that caused this position |
| `source_alert_id` | `uuid` | FK → `alerts.id` NULLABLE | Initial alert that triggered the copy |
| `opened_at` | `timestamptz` | NOT NULL, default `now()` | |
| `closed_at` | `timestamptz` | NULLABLE | Set when position is closed/resolved |

**Indexes:**
```sql
CREATE INDEX idx_paper_positions_portfolio ON paper_positions (portfolio_id, status);
CREATE INDEX idx_paper_positions_market ON paper_positions (market_id);
CREATE INDEX idx_paper_positions_followed ON paper_positions (followed_wallet);
```

---

## New Table: `paper_trades`

Individual simulated trade events (buys and sells).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | |
| `portfolio_id` | `uuid` | FK → `paper_portfolios.id` NOT NULL | |
| `position_id` | `uuid` | FK → `paper_positions.id` NULLABLE | Links to position |
| `source_alert_id` | `uuid` | FK → `alerts.id` NULLABLE | Original alert that triggered this |
| `market_id` | `text` | FK → `markets.id` NOT NULL | |
| `outcome` | `text` | NOT NULL | |
| `side` | `text` | NOT NULL, check in (`'BUY'`, `'SELL'`) | |
| `price` | `numeric(28,12)` | NOT NULL | Execution price (real market price) |
| `shares` | `numeric(28,12)` | NOT NULL | |
| `amount_usd` | `numeric(28,2)` | NOT NULL | price * shares |
| `followed_wallet` | `text` | FK → `wallets.wallet` NOT NULL | Source wallet |
| `copy_mode` | `text` | NULLABLE | `'proportional'` or `'fixed'` |
| `copy_value_used` | `numeric(28,6)` | NULLABLE | The value that was applied |
| `executed_at` | `timestamptz` | NOT NULL, default `now()` | |

**Indexes:**
```sql
CREATE INDEX idx_paper_trades_portfolio ON paper_trades (portfolio_id, executed_at DESC);
CREATE INDEX idx_paper_trades_market ON paper_trades (market_id);
CREATE INDEX idx_paper_trades_followed ON paper_trades (followed_wallet);
CREATE INDEX idx_paper_trades_source_alert ON paper_trades (source_alert_id);
```

---

## Modified Table: `wallet_analytics`

Add `follow_score` and `category_follow_scores` columns.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `follow_score` | `numeric(8,6)` | NULLABLE | Added in Phase 5 — how recommendable this wallet is to follow globally |
| `category_follow_scores` | `jsonb` | NULLABLE | Added in Phase 5 — per-category follow scores dict: `{"politics": 0.92, "crypto": 0.45}` |

---

## New Table: `wallet_category_follow_scores`

Per-category follow scores for each wallet. Allows querying "who should I follow in Politics?" without loading all wallets.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `wallet` | `text` | PK, FK → `wallets.wallet` | |
| `category` | `text` | PK, FK → `categories.category` | |
| `snapshot_date` | `date` | PK | |
| `follow_score` | `numeric(8,6)` | NOT NULL | Per-category follow score [0, 1] |
| `recommendation` | `text` | NOT NULL, check in (`'FOLLOW'`, `'WATCH'`, `'IGNORE'`) | Based on thresholds |
| `roi_percentile` | `numeric(8,6)` | NULLABLE | Wallet's ROI percentile in this category |
| `win_rate` | `numeric(8,6)` | NULLABLE | Win rate in this category |
| `is_specialist` | `boolean` | NOT NULL, default `false` | Whether wallet is specialist in this category |
| `volume_percentile` | `numeric(8,6)` | NULLABLE | Volume percentile in this category |
| `recency_days` | `integer` | NULLABLE | Days since last trade in this category |
| `reasons` | `jsonb` | NULLABLE | Array of reason strings |
| `global_follow_score` | `numeric(8,6)` | NULLABLE | Wallet's global follow_score (from wallet_analytics) for context |

**Indexes:**
```sql
CREATE INDEX idx_cat_follow_scores_score ON wallet_category_follow_scores (category, follow_score DESC);
CREATE INDEX idx_cat_follow_scores_wallet ON wallet_category_follow_scores (wallet, snapshot_date DESC);
CREATE INDEX idx_cat_follow_scores_recommendation ON wallet_category_follow_scores (category, recommendation)
    WHERE recommendation = 'FOLLOW';
```

**Unique constraint:** `(wallet, category, snapshot_date)` — one score per wallet per category per day.

---

## Migration Files

### Migration 018: `018_add_wallet_follows.py`

**Revision chain**: `017_add_edge_scoring.py` → `018_add_wallet_follows.py`

```python
"""Add wallet_follows table for Phase 5.

Revision ID: 018
Revises: 017
Create Date: 2026-06-29
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_follows",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_copy_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("copy_mode", sa.Text(), nullable=True),
        sa.Column("copy_value", sa.Numeric(28, 6), nullable=False, server_default=sa.text("0.05")),
        sa.Column("category_filter", postgresql.JSONB(), nullable=True),
        sa.Column("followed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("unfollowed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"], name="fk_follows_wallet"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "wallet", name="uq_follows_user_wallet"),
    )
    op.create_index("idx_follows_user_active", "wallet_follows", ["user_id", "active"],
                    postgresql_where=sa.text("active = true"))
    op.create_index("idx_follows_wallet", "wallet_follows", ["wallet"])
    op.create_index("idx_follows_auto_copy", "wallet_follows", ["auto_copy_enabled"],
                    postgresql_where=sa.text("auto_copy_enabled = true"))


def downgrade() -> None:
    op.drop_index("idx_follows_auto_copy", table_name="wallet_follows")
    op.drop_index("idx_follows_wallet", table_name="wallet_follows")
    op.drop_index("idx_follows_user_active", table_name="wallet_follows")
    op.drop_table("wallet_follows")
```

### Migration 019: `019_add_paper_trading.py`

**Revision chain**: `018_add_wallet_follows.py` → `019_add_paper_trading.py`

Creates `paper_portfolios`, `paper_positions`, `paper_trades`.

### Migration 020: `020_add_follow_score.py`

**Revision chain**: `019_add_paper_trading.py` → `020_add_follow_score.py`

```python
def upgrade() -> None:
    op.add_column(
        "wallet_analytics",
        sa.Column("follow_score", sa.Numeric(8, 6), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("wallet_analytics", "follow_score")
```

### Migration 021: `021_add_category_follow_scores.py`

**Revision chain**: `020_add_follow_score.py` → `021_add_category_follow_scores.py`

Adds `wallet_category_follow_scores` table and `category_follow_scores` JSONB column on `wallet_analytics`.

```python
"""Add wallet_category_follow_scores table for per-category follow recommendations.

Revision ID: 021
Revises: 020
Create Date: 2026-06-29
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_category_follow_scores",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("follow_score", sa.Numeric(8, 6), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("roi_percentile", sa.Numeric(8, 6), nullable=True),
        sa.Column("win_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("is_specialist", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("volume_percentile", sa.Numeric(8, 6), nullable=True),
        sa.Column("recency_days", sa.Integer(), nullable=True),
        sa.Column("reasons", postgresql.JSONB(), nullable=True),
        sa.Column("global_follow_score", sa.Numeric(8, 6), nullable=True),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"], name="fk_cat_follow_wallet"),
        sa.ForeignKeyConstraint(["category"], ["categories.category"], name="fk_cat_follow_category"),
        sa.PrimaryKeyConstraint("wallet", "category", "snapshot_date"),
    )
    op.create_index("idx_cat_follow_scores_score", "wallet_category_follow_scores",
                    ["category", sa.text("follow_score DESC")])
    op.create_index("idx_cat_follow_scores_wallet", "wallet_category_follow_scores",
                    ["wallet", sa.text("snapshot_date DESC")])
    op.create_index("idx_cat_follow_scores_rec", "wallet_category_follow_scores",
                    ["category", "recommendation"],
                    postgresql_where=sa.text("recommendation = 'FOLLOW'"))

    op.add_column(
        "wallet_analytics",
        sa.Column("category_follow_scores", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wallet_analytics", "category_follow_scores")
    op.drop_index("idx_cat_follow_scores_rec", table_name="wallet_category_follow_scores")
    op.drop_index("idx_cat_follow_scores_wallet", table_name="wallet_category_follow_scores")
    op.drop_index("idx_cat_follow_scores_score", table_name="wallet_category_follow_scores")
    op.drop_table("wallet_category_follow_scores")
```

---

## SQLAlchemy Models

Add to `app/db/models.py`:

```python
class WalletFollow(Base):
    __tablename__ = "wallet_follows"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    wallet = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    user_id = Column(Text, nullable=False)
    label = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, server_default=text("true"))
    auto_copy_enabled = Column(Boolean, nullable=False, server_default=text("false"))
    copy_mode = Column(Text, nullable=True)
    copy_value = Column(Numeric(28, 6), nullable=False, server_default=text("0.05"))
    category_filter = Column(JSONB, nullable=True)
    followed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    unfollowed_at = Column(DateTime(timezone=True), nullable=True)


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(Text, nullable=False)
    name = Column(Text, nullable=False, server_default=text("'Main'"))
    initial_balance = Column(Numeric(28, 2), nullable=False)
    current_balance = Column(Numeric(28, 2), nullable=False)
    total_realized_pnl = Column(Numeric(28, 2), nullable=False, server_default=text("0"))
    total_unrealized_pnl = Column(Numeric(28, 2), nullable=False, server_default=text("0"))
    total_pnl = Column(Numeric(28, 2), nullable=False, server_default=text("0"))
    total_roi = Column(Numeric(28, 6), nullable=True)
    total_trades = Column(Integer, nullable=False, server_default=text("0"))
    total_volume = Column(Numeric(28, 2), nullable=False, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    portfolio_id = Column(Uuid, ForeignKey("paper_portfolios.id"), nullable=False)
    market_id = Column(Text, ForeignKey("markets.id"), nullable=False)
    outcome = Column(Text, nullable=False)
    side = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'OPEN'"))
    shares = Column(Numeric(28, 12), nullable=False)
    avg_entry_price = Column(Numeric(28, 12), nullable=False)
    current_price = Column(Numeric(28, 12), nullable=True)
    cost_basis = Column(Numeric(28, 2), nullable=False)
    realized_pnl = Column(Numeric(28, 2), nullable=False, server_default=text("0"))
    unrealized_pnl = Column(Numeric(28, 2), nullable=True)
    followed_wallet = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    source_alert_id = Column(Uuid, ForeignKey("alerts.id"), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    portfolio_id = Column(Uuid, ForeignKey("paper_portfolios.id"), nullable=False)
    position_id = Column(Uuid, ForeignKey("paper_positions.id"), nullable=True)
    source_alert_id = Column(Uuid, ForeignKey("alerts.id"), nullable=True)
    market_id = Column(Text, ForeignKey("markets.id"), nullable=False)
    outcome = Column(Text, nullable=False)
    side = Column(Text, nullable=False)
    price = Column(Numeric(28, 12), nullable=False)
    shares = Column(Numeric(28, 12), nullable=False)
    amount_usd = Column(Numeric(28, 2), nullable=False)
    followed_wallet = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    copy_mode = Column(Text, nullable=True)
    copy_value_used = Column(Numeric(28, 6), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

### Add `follow_score` and `category_follow_scores` to `WalletAnalytic` model

```python
class WalletAnalytic(Base):
    __tablename__ = "wallet_analytics"
    # ... existing columns ...
    follow_score = Column(Numeric(8, 6), nullable=True)  # Phase 5
    category_follow_scores = Column(JSONB, nullable=True)  # Phase 5 — per-category scores
```


### New Model: `WalletCategoryFollowScore`

```python
class WalletCategoryFollowScore(Base):
    __tablename__ = "wallet_category_follow_scores"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    category = Column(Text, ForeignKey("categories.category"), primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    follow_score = Column(Numeric(8, 6), nullable=False)
    recommendation = Column(Text, nullable=False)
    roi_percentile = Column(Numeric(8, 6), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    is_specialist = Column(Boolean, nullable=False, server_default=text("false"))
    volume_percentile = Column(Numeric(8, 6), nullable=True)
    recency_days = Column(Integer, nullable=True)
    reasons = Column(JSONB, nullable=True)
    global_follow_score = Column(Numeric(8, 6), nullable=True)
```

---

## Pydantic Schemas

Add to `app/models/schemas.py`:

```python
# ── Phase 5: Follow ─────────────────────────────────────────────────

class FollowCreate(BaseModel):
    label: Optional[str] = None
    auto_copy_enabled: bool = False
    copy_mode: Optional[Literal["proportional", "fixed"]] = None
    copy_value: Decimal = Decimal("0.05")
    category_filter: Optional[list[str]] = None

    model_config = {"from_attributes": True}


class FollowUpdate(BaseModel):
    label: Optional[str] = None
    auto_copy_enabled: Optional[bool] = None
    copy_mode: Optional[Literal["proportional", "fixed"]] = None
    copy_value: Optional[Decimal] = None
    category_filter: Optional[list[str]] = None
    active: Optional[bool] = None


class FollowResponse(BaseModel):
    id: UUID
    wallet: str
    label: Optional[str] = None
    active: bool
    auto_copy_enabled: bool
    copy_mode: Optional[str] = None
    copy_value: Decimal
    category_filter: Optional[list[str]] = None
    followed_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FollowListResponse(BaseModel):
    data: list[FollowResponse]
    total: int


class FollowRecommendation(BaseModel):
    wallet: str
    follow_score: Decimal
    reasons: list[str]


class FollowRecommendationResponse(BaseModel):
    data: list[FollowRecommendation]
    limit: int
    offset: int


# ── Phase 5: Paper Trading ──────────────────────────────────────────

class PortfolioResponse(BaseModel):
    id: UUID
    name: str
    initial_balance: Decimal
    current_balance: Decimal
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    total_pnl: Decimal
    total_roi: Optional[Decimal] = None
    total_trades: int
    total_volume: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaperPositionResponse(BaseModel):
    id: UUID
    market_id: str
    outcome: str
    side: str
    status: str
    shares: Decimal
    avg_entry_price: Decimal
    current_price: Optional[Decimal] = None
    cost_basis: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Optional[Decimal] = None
    followed_wallet: str
    opened_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaperPositionListResponse(BaseModel):
    data: list[PaperPositionResponse]
    total: int


class PaperTradeResponse(BaseModel):
    id: UUID
    market_id: str
    outcome: str
    side: str
    price: Decimal
    shares: Decimal
    amount_usd: Decimal
    followed_wallet: str
    copy_mode: Optional[str] = None
    copy_value_used: Optional[Decimal] = None
    executed_at: datetime

    model_config = {"from_attributes": True}


class PaperTradeListResponse(BaseModel):
    data: list[PaperTradeResponse]
    limit: int
    offset: int
    total: int


class PortfolioResetRequest(BaseModel):
    initial_balance: Decimal = Field(default=Decimal("10000"), gt=0)


class PortfolioResetResponse(BaseModel):
    portfolio: PortfolioResponse
    message: str


# ── Phase 5: Per-Category Follow Scores ─────────────────────────────

class CategoryFollowScoreItem(BaseModel):
    category: str
    follow_score: Decimal
    recommendation: str  # FOLLOW / WATCH / IGNORE
    roi_percentile: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    is_specialist: bool = False
    volume_percentile: Optional[Decimal] = None
    recency_days: Optional[int] = None
    reasons: list[str] = []

    model_config = {"from_attributes": True}


class WalletCategoryFollowScoresResponse(BaseModel):
    wallet: str
    global_follow_score: Optional[Decimal] = None
    category_scores: list[CategoryFollowScoreItem]


class CategoryFollowLeaderboardEntry(BaseModel):
    wallet: str
    follow_score: Decimal
    recommendation: str
    roi_percentile: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    is_specialist: bool = False
    reasons: list[str] = []


class CategoryFollowLeaderboardResponse(BaseModel):
    category: str
    data: list[CategoryFollowLeaderboardEntry]
    limit: int
    offset: int
```

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `alembic/versions/018_add_wallet_follows.py` |
| CREATE | `alembic/versions/019_add_paper_trading.py` |
| CREATE | `alembic/versions/020_add_follow_score.py` |
| CREATE | `alembic/versions/021_add_category_follow_scores.py` |
| EDIT | `app/db/models.py` — add `WalletFollow`, `PaperPortfolio`, `PaperPosition`, `PaperTrade`, `WalletCategoryFollowScore`; add `follow_score` + `category_follow_scores` to `WalletAnalytic` |
| EDIT | `app/models/schemas.py` — add all schemas above |
| RUN | `alembic upgrade head` |

---

## Verification

```bash
alembic upgrade head          # apply 018 → 019 → 020 → 021
alembic downgrade -4          # rollback all four
alembic upgrade head          # re-apply, no errors
psql -U app -d polymarket -c "\d wallet_follows"
psql -U app -d polymarket -c "\d paper_portfolios"
psql -U app -d polymarket -c "\d paper_positions"
psql -U app -d polymarket -c "\d paper_trades"
psql -U app -d polymarket -c "\d wallet_category_follow_scores"
psql -U app -d polymarket -c "\d wallet_analytics"  # verify follow_score + category_follow_scores
```
