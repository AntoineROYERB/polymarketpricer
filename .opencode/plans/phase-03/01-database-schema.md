# Phase 3 — Smart Money Detection — Database Schema

> **Goal**: Store detected high-signal trades and configurable alert rules.
> **AI Agent Instructions**: Create the migration file `alembic/versions/005_smart_money_alerts.py`, add models to `app/db/models.py`, and update Pydantic schemas in `app/models/schemas.py`.

---

## New Tables

### `alerts`

Stores every detected high-signal trading event before Discord notification.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `uuid` | PK, `gen_random_uuid()` | Auto-generated |
| `wallet` | `text` | FK → `wallets.wallet` NOT NULL | Trader address |
| `market_id` | `text` | FK → `markets.id` NOT NULL | Market ID |
| `action` | `text` | NOT NULL | `NEW_POSITION`, `POSITION_INCREASE`, `POSITION_DECREASE`, `FULL_EXIT` |
| `price` | `numeric(28,12)` | NOT NULL | Entry/exit price |
| `position_size` | `numeric(28,2)` | NOT NULL | USD magnitude of this change |
| `wallet_score` | `numeric(8,6)` | NOT NULL | Score at detection time |
| `category` | `text` | NOT NULL | Market's `mapped_category` |
| `market_question` | `text` | NOT NULL | Denormalized for payload |
| `detected_at` | `timestamptz` | NOT NULL, default `now()` | When system detected |
| `notified_at` | `timestamptz` | NULLABLE | Set after Discord delivery |
| `delivery_attempts` | `int` | NOT NULL, default 0 | Retry counter |

**Indexes:**

```sql
CREATE INDEX idx_alerts_detected_at ON alerts (detected_at DESC);
CREATE INDEX idx_alerts_wallet ON alerts (wallet);
CREATE INDEX idx_alerts_category ON alerts (category);
CREATE INDEX idx_alerts_unnotified ON alerts (detected_at) WHERE notified_at IS NULL;
CREATE INDEX idx_alerts_wallet_market ON alerts (wallet, market_id);
```

### `alert_rules`

Threshold configuration. A row with `wallet IS NULL` acts as the global default.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `uuid` | PK, `gen_random_uuid()` | |
| `wallet` | `text` | NULLABLE, UNIQUE | NULL = global default |
| `min_score` | `numeric(8,6)` | NOT NULL, default 80.0 | |
| `min_position_size` | `numeric(28,2)` | NOT NULL, default 500 | USD |
| `min_liquidity` | `numeric(28,2)` | NOT NULL, default 1000 | Market liquidity USD |
| `cooldown_minutes` | `int` | NOT NULL, default 15 | Dedup window |
| `discord_webhook_url` | `text` | NULLABLE | Per-wallet override |
| `active` | `boolean` | NOT NULL, default true | |

---

## Migration File (`005_smart_money_alerts.py`)

**Revision chain**: `004_add_categories_table.py` → `005_smart_money_alerts.py`

```python
"""Add alerts and alert_rules tables for Phase 3 Smart Money Detection.

Revision ID: 005
Revises: 004
Create Date: 2026-06-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("wallet", sa.Text(), nullable=True, unique=True),
        sa.Column("min_score", sa.Numeric(8, 6), nullable=False, server_default=sa.text("80.0")),
        sa.Column("min_position_size", sa.Numeric(28, 2), nullable=False, server_default=sa.text("500")),
        sa.Column("min_liquidity", sa.Numeric(28, 2), nullable=False, server_default=sa.text("1000")),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default=sa.text("15")),
        sa.Column("discord_webhook_url", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=False),
        sa.Column("position_size", sa.Numeric(28, 2), nullable=False),
        sa.Column("wallet_score", sa.Numeric(8, 6), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("market_question", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"], name="fk_alerts_wallet"),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"], name="fk_alerts_market"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_alerts_detected_at", "alerts", [sa.text("detected_at DESC")])
    op.create_index("idx_alerts_wallet", "alerts", ["wallet"])
    op.create_index("idx_alerts_category", "alerts", ["category"])
    op.create_index(
        "idx_alerts_unnotified",
        "alerts",
        ["detected_at"],
        postgresql_where=sa.text("notified_at IS NULL"),
    )
    op.create_index("idx_alerts_wallet_market", "alerts", ["wallet", "market_id"])

    # Seed global default rule
    op.execute("""
        INSERT INTO alert_rules (wallet, min_score, min_position_size, min_liquidity, cooldown_minutes)
        VALUES (NULL, 80.0, 500, 1000, 15)
    """)


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("alert_rules")
```

---

## SQLAlchemy Models

Add to `app/db/models.py` — insert after the `CategoryRanking` class (before the file ends):

```python
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    wallet = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    market_id = Column(Text, ForeignKey("markets.id"), nullable=False)
    action = Column(Text, nullable=False)
    price = Column(Numeric(28, 12), nullable=False)
    position_size = Column(Numeric(28, 2), nullable=False)
    wallet_score = Column(Numeric(8, 6), nullable=False)
    category = Column(Text, nullable=False)
    market_question = Column(Text, nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notified_at = Column(DateTime(timezone=True), nullable=True)
    delivery_attempts = Column(Integer, nullable=False, server_default=text("0"))


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    wallet = Column(Text, nullable=True, unique=True)
    min_score = Column(Numeric(8, 6), nullable=False, server_default=text("80.0"))
    min_position_size = Column(Numeric(28, 2), nullable=False, server_default=text("500"))
    min_liquidity = Column(Numeric(28, 2), nullable=False, server_default=text("1000"))
    cooldown_minutes = Column(Integer, nullable=False, server_default=text("15"))
    discord_webhook_url = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, server_default=text("true"))
```

**Required imports** at the top of `app/db/models.py` — ensure `Uuid` is imported:

```python
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Index,
    Integer, Interval, Numeric, Text, Uuid, func, text,
)
```

---

## Pydantic Schemas

Add to `app/models/schemas.py` — insert before `LeaderboardEntry` (or at the end):

```python
from enum import Enum


class AlertAction(str, Enum):
    NEW_POSITION = "NEW_POSITION"
    POSITION_INCREASE = "POSITION_INCREASE"
    POSITION_DECREASE = "POSITION_DECREASE"
    FULL_EXIT = "FULL_EXIT"


class AlertItem(BaseModel):
    id: str
    wallet: str
    market_id: str
    market_question: str
    action: AlertAction
    price: Decimal
    position_size: Decimal
    wallet_score: Decimal
    category: str
    detected_at: datetime
    notified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    data: list[AlertItem]
    limit: int
    offset: int
```

---

## Files to Create / Modify

| Action | Path |
|---|---|
| CREATE | `alembic/versions/005_smart_money_alerts.py` |
| EDIT | `app/db/models.py` — add `Alert`, `AlertRule` classes; add `Uuid` import |
| EDIT | `app/models/schemas.py` — add `AlertAction`, `AlertItem`, `AlertListResponse` |
| RUN | `alembic upgrade head` |

---

## Verification

```bash
alembic upgrade head            # should apply 005
alembic downgrade -1            # should drop alerts + alert_rules
alembic upgrade head            # re-apply, no errors
psql -U app -d polymarket -c "\d alerts"          # verify columns
psql -U app -d polymarket -c "SELECT * FROM alert_rules;"  # verify global default seed row
```
