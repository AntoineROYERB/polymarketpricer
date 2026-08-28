# Phase 2 — ETL Pipeline: Category Analytics

> **Goal**: New Mage AI pipeline to compute per-category metrics for every tracked wallet.
> **Pattern**: Mirrors `enrichment_analytics_computation` + `enrichment_ranking_computation` but grouped by category.
> **Status**: Planning — ready for spec.

---

## 1. Pipeline Overview

**Name**: `category_analytics`
**SLA**: 120s (larger dataset than global analytics due to per-category grouping)

### Block DAG

```
load_recent_wallets ─┬─→ load_positions_data ─┬─→ compute_category_metrics ──→ export_category_analytics
                     └─→ load_trades_data ────┘         │
                     ─→ load_market_categories ──────────┘
```

### Blocks

| Block | Type | Purpose |
|---|---|---|
| `load_recent_wallets` | Data Loader | Wallets with recent activity (reuses existing query) |
| `load_positions_data` | Data Loader | Positions for those wallets |
| `load_trades_data` | Data Loader | Trades for those wallets |
| `load_market_categories` | Data Loader | Market → `mapped_category` mapping |
| `compute_category_metrics` | Transformer | Per-category metrics per wallet; specialist detection |
| `export_category_analytics` | Data Exporter | Upsert into `category_analytics` + `category_rankings` |

---

## 2. Data Loaders

### `load_recent_wallets.py`

Same as existing `load_recent_activity.py` — query for wallets with recent trades or updated positions. No changes needed.

### `load_positions_data.py`

Same as existing — positions for the selected wallets. No changes needed.

### `load_trades_data.py`

Same as existing — trades for the selected wallets. No changes needed.

### `load_market_categories.py` (NEW)

Query all markets to build the `market_id → mapped_category` lookup:

```sql
SELECT id, mapped_category FROM markets WHERE mapped_category IS NOT NULL
```

Output: DataFrame with columns `[market_id, category]`.

---

## 3. Transformer: `compute_category_metrics.py`

Core logic — group trades and positions by (wallet, category), then compute the same metrics as `compute_wallet_metrics.py` within each group.

### Algorithm

```python
def compute_category_metrics(
    trades: DataFrame,
    positions: DataFrame,
    market_categories: dict[str, str],
) -> DataFrame:
```

1. **Join trades with categories**: Left-join trades → market_categories on `market_id`
2. **Drop unclassified trades**: Where category is NULL (can't assign to a category)
3. **Group by (wallet, category)**: For each group, compute:
   - `num_trades` — count of trades
   - `total_volume` — sum of |amount_usd|
   - `total_cost_basis` — sum of cost basis
   - `total_pnl` — realized + unrealized from positions in this category
   - `roi` — total_pnl / total_cost_basis × 100
   - `win_rate` — resolved wins / resolved total in category
   - `profit_factor` — gross profit / |gross loss|
   - `avg_position_size` — total_volume / num_trades
   - `avg_holding_duration` — average exit_time - entry_time for resolved positions
4. **Filter**: Keep only wallets with ≥ 30 trades in the category (expertise threshold)
5. **Mark specialists**: For each category, compute median ROI and median volume. A wallet is a specialist if:
   - Trades in category ≥ 30
   - Category ROI > category median ROI
   - Category volume > category median volume

### Metric Reuse

Most of the per-wallet metric functions from `compute_wallet_metrics.py` can be reused. The key difference is that we group by (wallet, category) instead of just wallet.

### Output Schema

```python
{
    "wallet": str,
    "category": str,
    "snapshot_date": date,
    "num_trades": int,
    "total_volume": Decimal,
    "total_cost_basis": Decimal,
    "total_pnl": Decimal,
    "total_realized_pnl": Decimal,
    "total_unrealized_pnl": Decimal,
    "roi": Decimal | None,
    "win_rate": Decimal | None,
    "num_resolved_positions": int,
    "profit_factor": Decimal | None,
    "avg_position_size": Decimal | None,
    "avg_holding_duration": float | None,  # seconds
    "is_specialist": bool,
    "category_rank": int | None,
}
```

---

## 4. Ranking Step

After computing all per-category metrics:

1. **Per-category ranking**: Rank wallets within each category by `roi` (descending)
2. **Top 50 per category**: Materialize the top 50 wallets per category into `category_rankings` with `list_type = 'top_50'`
3. **Specialists**: Materialize all specialists (from any category) into `category_rankings` with `list_type = 'specialists'`

---

## 5. Data Exporter: `export_category_analytics.py`

### Step 1 — Upsert `category_analytics`

```sql
INSERT INTO category_analytics (...) VALUES (...) 
ON CONFLICT (wallet, category, snapshot_date) DO UPDATE SET ...
```

### Step 2 — Replace `category_rankings` for today

```sql
DELETE FROM category_rankings WHERE snapshot_date = CURRENT_DATE;

INSERT INTO category_rankings (...) VALUES (...);
```

---

## 6. Pipeline Registration

### `magic/default_repo/pipelines/category_analytics/metadata.yaml`

New pipeline definition following the same YAML format as existing pipelines.

### `magic/scripts/run_all.py` — Add Phase 6

Insert the new pipeline into the orchestrator:

```python
# New Phase 6: category_analytics
run_pipeline("category_analytics", run_category_analytics)

# Renumber existing Phase 6 → Phase 7
```

```python
def run_category_analytics():
    from data_loaders.load_recent_activity import load_data_from_api as load_wallets
    from data_loaders.load_positions_data import load_data_from_api as load_positions
    from data_loaders.load_trades_data import load_data_from_api as load_trades
    from data_loaders.load_market_categories import load_data_from_api as load_categories
    from transformers.compute_category_metrics import transform_df
    from data_exporters.export_category_analytics import export_data

    wallets = load_wallets()
    positions = load_positions(wallets)
    trades = load_trades(wallets)
    categories = load_categories()
    metrics = transform_df(positions, trades, categories)
    export_data(metrics)
```

---

## 7. Update to `ingestion_market_discovery` Pipeline

Add category inference to the `merge_markets` transformer in `ingestion_market_discovery`:

1. After merging active + resolved markets, apply `infer_category()` to each market
2. Set `mapped_category` column on the output DataFrame
3. Update the `export_markets` exporter to write `mapped_category` to the database

---

## 8. Acceptance Criteria

- [ ] Pipeline runs end-to-end with no errors
- [ ] `category_analytics` table populated with per-category rows
- [ ] `category_rankings` table populated with top 50 per category + specialists
- [ ] At least 100 wallets have category data (across all categories)
- [ ] No wallet has duplicate (wallet, category, snapshot_date) rows
- [ ] `roi` values are within sensible ranges (e.g., -100% to +10000%)
- [ ] `win_rate` values are within [0, 1]
- [ ] `is_specialist` is True only for wallets meeting all 3 criteria
- [ ] Pipeline completes within 120s SLA
- [ ] Existing 6 pipelines still run correctly
