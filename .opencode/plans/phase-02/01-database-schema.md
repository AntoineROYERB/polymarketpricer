# Phase 2 — Database Schema: Category Analytics

> **Goal**: Add tables to store per-category wallet analytics and category-specific rankings.
> **Status**: Planning — ready for spec.

---

## 1. New Tables

### `category_analytics` (NEW)

Per-wallet, per-category, per-day analytical snapshot.

| Column | Type | Notes |
|---|---|---|
| `wallet` | Text → FK → wallets.wallet | PK |
| `category` | Text | PK — one of the 8 target categories |
| `snapshot_date` | Date | PK |
| `num_trades` | Integer | Trade count in this category |
| `total_volume` | Numeric(28, 2) | Sum of \|amount_usd\| for trades in this category |
| `total_cost_basis` | Numeric(28, 2) | Sum of cost basis |
| `total_pnl` | Numeric(28, 2) | Realized + unrealized PnL in this category |
| `total_realized_pnl` | Numeric(28, 2) | Realized PnL only |
| `total_unrealized_pnl` | Numeric(28, 2) | Unrealized PnL only |
| `roi` | Numeric(8, 6) | ROI = total_pnl / total_cost_basis × 100 |
| `win_rate` | Numeric(8, 6) | Wins / resolved positions in category |
| `num_resolved_positions` | Integer | Resolved positions count |
| `profit_factor` | Numeric(28, 6) | Gross profit / \|gross loss\| |
| `avg_position_size` | Numeric(28, 2) | Average position size in category |
| `avg_holding_duration` | Interval | Average holding time |
| `is_specialist` | Boolean | True if expertise criteria met |
| `category_rank` | Integer | Rank within category (set during ranking step) |

**Indexes:**
- `(snapshot_date, category, category_rank)` — for leaderboard queries
- `(wallet, snapshot_date)` — for wallet profile queries

---

### `category_rankings` (NEW)

Materialized leaderboard lists per category (similar to `ranking_snapshots`).

| Column | Type | Notes |
|---|---|---|
| `wallet` | Text → FK → wallets.wallet | PK |
| `category` | Text | PK |
| `snapshot_date` | Date | PK |
| `list_type` | Text | PK — `top_50`, `specialists` |
| `rank` | Integer | |
| `wallet_score` | Numeric(8, 6) | Overall wallet score from Phase 1 |
| `roi` | Numeric(8, 6) | Category ROI |
| `win_rate` | Numeric(8, 6) | Category win rate |
| `total_pnl` | Numeric(28, 2) | Category PnL |
| `num_trades` | Integer | Category trade count |
| `total_volume` | Numeric(28, 2) | Category volume |

**Indexes:**
- `(snapshot_date, category, list_type, rank)` — for leaderboard queries

---

## 2. Migration: `002_category_analytics.py`

New Alembic migration (not a squash — Phase 1 data must be preserved).

```python
revision = "002"
down_revision = "001"

def upgrade():
    op.create_table("category_analytics", …)
    op.create_table("category_rankings", …)
    # indexes + FKs

def downgrade():
    op.drop_table("category_rankings")
    op.drop_table("category_analytics")
```

---

## 3. SQLAlchemy Models

New models in `app/db/models.py`:

- `class CategoryAnalytic(Base)` — maps to `category_analytics`
- `class CategoryRanking(Base)` — maps to `category_rankings`

---

## 4. Impact on Existing Code

| File | Change |
|---|---|
| `app/db/models.py` | Add `CategoryAnalytic` + `CategoryRanking` models |
| `alembic/versions/002_category_analytics.py` | New migration (new file) |
| `app/models/schemas.py` | Add `CategoryAnalyticsData`, `CategoryLeaderboardEntry`, `CategoryLeaderboardResponse` |
| `app/models/enums.py` | Already has `MarketCategory` — no change needed |

---

## 5. Acceptance Criteria

- [ ] `alembic upgrade head` creates both tables with correct columns, FKs, and indexes
- [ ] `alembic downgrade -1` drops both tables cleanly
- [ ] Models can be imported without circular dependency errors
- [ ] Existing Phase 1 data is untouched
- [ ] All 41 existing tests still pass
