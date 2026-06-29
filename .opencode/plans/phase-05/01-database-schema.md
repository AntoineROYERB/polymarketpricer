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

Add `follow_score` column.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `follow_score` | `numeric(8,6)` | NULLABLE | Added in Phase 5 — how recommendable this wallet is to follow |

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

### Add `follow_score` to `WalletAnalytic` model

```python
class WalletAnalytic(Base):
    __tablename__ = "wallet_analytics"
    # ... existing columns ...
    follow_score = Column(Numeric(8, 6), nullable=True)  # Phase 5
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
```

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `alembic/versions/018_add_wallet_follows.py` |
| CREATE | `alembic/versions/019_add_paper_trading.py` |
| CREATE | `alembic/versions/020_add_follow_score.py` |
| EDIT | `app/db/models.py` — add `WalletFollow`, `PaperPortfolio`, `PaperPosition`, `PaperTrade`; add `follow_score` to `WalletAnalytic` |
| EDIT | `app/models/schemas.py` — add all schemas above |
| RUN | `alembic upgrade head` |

---

## Verification

```bash
alembic upgrade head          # apply 018 → 019 → 020
alembic downgrade -3          # rollback all three
alembic upgrade head          # re-apply, no errors
psql -U app -d polymarket -c "\d wallet_follows"
psql -U app -d polymarket -c "\d paper_portfolios"
psql -U app -d polymarket -c "\d paper_positions"
psql -U app -d polymarket -c "\d paper_trades"
psql -U app -d polymarket -c "\d wallet_analytics"  # verify follow_score
```
