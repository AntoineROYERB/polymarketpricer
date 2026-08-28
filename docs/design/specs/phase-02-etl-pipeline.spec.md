# Phase 2 — ETL Pipeline Implementation Spec: `category_analytics`

> **Status**: Final Draft  
> **Target**: PolymarketPricer v0.2.0  
> **SLA**: 120s (pipeline), 30s (ranking step within exporter)  
> **Prerequisite**: Alembic migration `002_category_analytics` applied (adds `markets.mapped_category`, `category_analytics`, `category_rankings` tables)

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [Directory Structure](#2-directory-structure)
3. [metadata.yaml](#3-metadatayaml)
4. [load_market_categories.py (Data Loader)](#4-load_market_categoriespy-data-loader)
5. [compute_category_metrics.py (Transformer)](#5-compute_category_metricspy-transformer)
6. [export_category_analytics.py (Data Exporter)](#6-export_category_analyticspy-data-exporter)
7. [Orchestrator Update: run_all.py](#7-orchestrator-update-run_allpy)
8. [Prerequisites & Dependencies](#8-prerequisites--dependencies)
9. [Backfill & Historical Data](#9-backfill--historical-data)
10. [Error Handling & Edge Cases](#10-error-handling--edge-cases)
11. [Acceptance Criteria](#11-acceptance-criteria)

---

## 1. Pipeline Overview

**Pipeline UUID**: `category_analytics`  
**Type**: `python`  
**Description**: Computes per-category wallet analytics by grouping trades and positions by (wallet, category), computing standard metrics within each group, detecting specialist wallets, and materialising ranked leaderboards.

### DAG

```
load_recent_wallets ─┬─→ load_positions_data ─┬─→ compute_category_metrics ──→ export_category_analytics
                     │                        │         ↑
                     └─→ load_trades_data ─────┘         │
                     ─→ load_market_categories ──────────┘
```

### Block Table

| Block name | Type | Purpose | Input from |
|---|---|---|---|
| `load_recent_wallets` | Data Loader | Wallets with trades in last 24h | (none) |
| `load_positions_data` | Data Loader | Positions for those wallets | `load_recent_wallets` |
| `load_trades_data` | Data Loader | Trades for those wallets | `load_recent_wallets` |
| `load_market_categories` | Data Loader | market_id → mapped_category mapping | (none) |
| `compute_category_metrics` | Transformer | Per-(wallet,category) metrics | `load_positions_data`, `load_trades_data`, `load_market_categories` |
| `export_category_analytics` | Data Exporter | Upsert `category_analytics` + materialise `category_rankings` | `compute_category_metrics` |

### Reuse Strategy

- **`load_recent_wallets`**: Reuses the existing `load_recent_activity.py` data_loader **unchanged** (query for wallets with recent trades).
- **`load_positions_data`**: Reuses the existing `load_positions_data.py` data_loader **unchanged**.
- **`load_trades_data`**: Reuses the existing `load_trades_data.py` data_loader **unchanged**.
- **`compute_wallet_metrics.py` helpers**: The transformer imports `safe_div` from the existing module and follows the same metric computation logic. No code duplication for PnL, ROI, win_rate, profit_factor, avg_position_size, or avg_holding_duration arithmetic.

---

## 2. Directory Structure

Create the following new files:

```
magic/default_repo/pipelines/category_analytics/
    __init__.py                          # empty file
    metadata.yaml                        # pipeline definition
    triggers/
        default.yaml                     # API trigger definition

magic/default_repo/data_loaders/
    load_market_categories.py            # NEW loader

magic/default_repo/transformers/
    compute_category_metrics.py          # NEW transformer

magic/default_repo/data_exporters/
    export_category_analytics.py         # NEW exporter
```

**No changes** to existing loaders (`load_recent_activity.py`, `load_positions_data.py`, `load_trades_data.py`).

---

## 3. metadata.yaml

```yaml
blocks:
- all_upstream_blocks_executed: true
  color: null
  configuration: {}
  downstream_blocks:
  - load_positions_data
  - load_trades_data
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: load_recent_wallets
  retry_config: null
  status: not_executed
  timeout: null
  type: data_loader
  upstream_blocks: []
  uuid: load_recent_wallets
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks:
  - compute_category_metrics
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: load_positions_data
  retry_config: null
  status: not_executed
  timeout: null
  type: data_loader
  upstream_blocks:
  - load_recent_wallets
  uuid: load_positions_data
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks:
  - compute_category_metrics
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: load_trades_data
  retry_config: null
  status: not_executed
  timeout: null
  type: data_loader
  upstream_blocks:
  - load_recent_wallets
  uuid: load_trades_data
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks:
  - compute_category_metrics
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: load_market_categories
  retry_config: null
  status: not_executed
  timeout: null
  type: data_loader
  upstream_blocks: []
  uuid: load_market_categories
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks:
  - export_category_analytics
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: compute_category_metrics
  retry_config: null
  status: not_executed
  timeout: null
  type: transformer
  upstream_blocks:
  - load_positions_data
  - load_trades_data
  - load_market_categories
  uuid: compute_category_metrics
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks: []
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: export_category_analytics
  retry_config: null
  status: not_executed
  timeout: null
  type: data_exporter
  upstream_blocks:
  - compute_category_metrics
  uuid: export_category_analytics
cache_block_output_in_memory: false
callbacks: []
concurrency_config: {}
conditionals: []
created_at: null
data_integration: null
description: Per-category wallet analytics – computes metrics grouped by (wallet,
  category), detects specialists, and materialises top-50 leaderboards.
executor_config: {}
executor_count: 1
executor_type: null
extensions: {}
name: category_analytics
notification_config: {}
remote_variables_dir: null
retry_config: {}
run_pipeline_in_one_process: false
settings:
  triggers:
  - POLYMARKET_TRIGGER_CATEGORY_ANALYTICS_SCHEDULE
spark_config: {}
tags: []
type: python
uuid: category_analytics
variables_dir: /home/src/mage_data/default_repo
widgets: []
```

**Triggers file** `triggers/default.yaml`:

```yaml
name: POLYMARKET_TRIGGER_CATEGORY_ANALYTICS_SCHEDULE
pipeline_uuid: category_analytics
schedule_interval: null
schedule_type: api
status: active

variables:
  run_date: "{{ execution_date }}"

settings:
  sla: 120
```

---

## 4. load_market_categories.py (Data Loader)

### Purpose

Queries the `markets` table to build a mapping of `market_id → mapped_category`. This mapping is used by the transformer to classify trades and positions into one of the 8 target categories.

### Design Decisions

- `mapped_category` is populated by the `ingestion_market_discovery` pipeline's `merge_markets` transformer (see Phase 2 Category Mapping plan — Option A). If the column is `NULL` for a market, it means the classifier could not determine a category; such markets are excluded from category analytics but remain in global analytics.
- The loader queries **all** markets (not just recent ones) to ensure every trade/position can be classified, even if the market was loaded in a previous pipeline run.
- Returns a DataFrame with columns `[market_id, category]`.

### Code

```python
from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_loader
def load_data_from_api(*args, **kwargs) -> DataFrame:
    """Load (market_id, mapped_category) for all classified markets."""
    engine = create_engine(DATABASE_URL)
    df = read_sql(
        text("""
            SELECT id AS market_id, mapped_category AS category
            FROM markets
            WHERE mapped_category IS NOT NULL
        """),
        engine,
    )
    engine.dispose()
    print(f"Loaded {len(df)} market→category mappings")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
    assert 'market_id' in df.columns, "Missing market_id column"
    assert 'category' in df.columns, "Missing category column"
```

---

## 5. compute_category_metrics.py (Transformer)

### Purpose

Accepts three DataFrames (trades, positions, market_categories), joins each with market categories, groups by (wallet, category), and computes standardised metrics for each group. Detects specialist wallets and ranks wallets within each category.

### Algorithm

```
1. Left-join trades → market_categories on market_id
2. Left-join positions → market_categories on market_id
3. Drop rows where category IS NULL (unclassified)
4. For each (wallet, category) group:
   a. Filter trades and positions to this wallet + category
   b. Compute per-wallet metrics (calling compute_metrics_for_wallet_category)
   c. Apply 30-trade minimum threshold
   d. Accumulate row
5. Post-processing:
   a. Compute category-level median ROI and median volume
   b. Mark specialists: ROI > median AND volume > median
   c. Rank wallets within each category by ROI (descending)
6. Return DataFrame matching category_analytics table schema
```

### Helper Reuse

- `from transformers.compute_wallet_metrics import safe_div` — reused directly.
- Metric computation logic (PnL, ROI, win_rate, profit_factor formulas) follows the exact same arithmetic as `compute_metrics_for_wallet` but is distilled into a leaner `compute_metrics_for_wallet_category` function with per-category thresholds.

### Threshold Constants

```python
MIN_CATEGORY_TRADES = 30       # Minimum trades in a category to be included
```

No minimum volume or history age at the category level — the wallet-level global filtering (from `should_include` in `compute_wallet_metrics.py`) is a separate concern applied by the `enrichment_analytics_computation` pipeline.

### Code

```python
import math
from datetime import date
from typing import Optional

from pandas import DataFrame, isna, to_numeric, NaT

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

# Reuse the safe_div helper from the existing wallet metrics module.
from transformers.compute_wallet_metrics import safe_div

MIN_CATEGORY_TRADES = 30


def compute_metrics_for_wallet_category(
    wallet: str,
    category: str,
    trades: DataFrame,
    positions: DataFrame,
) -> Optional[dict]:
    """Compute per-category metrics for a single (wallet, category) pair.

    Mirrors the logic in compute_metrics_for_wallet() but scoped to a specific
    category and with a lower trade threshold (30 vs 50). Does NOT compute
    sharpe_ratio, max_drawdown, consistency_score, experience_score, or wallet_score
    at the category level.

    Returns a dict matching the category_analytics table schema, or None if the
    wallet does not meet the minimum trade threshold in this category.
    """
    today = date.today()

    total_realized_pnl = 0.0
    total_unrealized_pnl = 0.0
    total_cost_basis = 0.0
    total_volume = 0.0
    num_trades = 0
    resolved_wins = 0
    resolved_total = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_holding_seconds = 0.0
    holding_count = 0

    category_trades = trades[
        (trades["wallet"] == wallet) & (trades["category"] == category)
    ].copy() if not trades.empty else DataFrame()

    category_positions = positions[
        (positions["wallet"] == wallet) & (positions["category"] == category)
    ].copy() if not positions.empty else DataFrame()

    # ── Trade metrics ──────────────────────────────────────────────
    if not category_trades.empty:
        category_trades["amount_usd"] = to_numeric(
            category_trades["amount_usd"], errors="coerce"
        ).fillna(0)
        category_trades["price"] = to_numeric(
            category_trades["price"], errors="coerce"
        ).fillna(0)
        category_trades["shares"] = to_numeric(
            category_trades["shares"], errors="coerce"
        ).fillna(0)
        category_trades["fee_usd"] = to_numeric(
            category_trades["fee_usd"], errors="coerce"
        ).fillna(0)

        num_trades = len(category_trades)
        total_volume = float(category_trades["amount_usd"].abs().sum())

        buys = category_trades[category_trades["side"] == "BUY"]
        sells = category_trades[category_trades["side"] == "SELL"]
        total_cost_basis = float(
            (buys["price"] * buys["shares"]).sum()
            + (sells["price"] * sells["shares"]).abs().sum()
        )

    # ── Position metrics ───────────────────────────────────────────
    if not category_positions.empty:
        category_positions["realized_pnl"] = to_numeric(
            category_positions["realized_pnl"], errors="coerce"
        ).fillna(0)
        category_positions["unrealized_pnl"] = to_numeric(
            category_positions["unrealized_pnl"], errors="coerce"
        ).fillna(0)
        category_positions["total_pnl"] = to_numeric(
            category_positions["total_pnl"], errors="coerce"
        ).fillna(0)

        total_realized_pnl = float(category_positions["realized_pnl"].sum())
        total_unrealized_pnl = float(category_positions["unrealized_pnl"].sum())

        resolved = category_positions[
            category_positions["status"].isin(["RESOLVED", "CLOSED"])
        ]
        resolved_total = len(resolved)
        resolved_wins = int((resolved["realized_pnl"] > 0).sum())

        for _, p in resolved.iterrows():
            pnl = float(p["realized_pnl"])
            if pnl > 0:
                gross_profit += pnl
            elif pnl < 0:
                gross_loss += abs(pnl)

        for _, p in resolved.iterrows():
            et = p.get("entry_time")
            xt = p.get("exit_time")
            if et and xt and et is not NaT and xt is not NaT:
                delta = (xt - et).total_seconds()
                if delta > 0:
                    total_holding_seconds += delta
                    holding_count += 1

    total_pnl = total_realized_pnl + total_unrealized_pnl

    # ── Derived metrics ────────────────────────────────────────────
    roi = safe_div(total_pnl, total_cost_basis) * 100 if total_cost_basis else None
    if roi is not None:
        roi = round(roi, 6)

    win_rate = safe_div(resolved_wins, resolved_total)
    if win_rate is not None:
        win_rate = round(win_rate, 6)

    profit_factor = safe_div(gross_profit, gross_loss) if gross_loss > 0 else None
    if profit_factor is not None:
        profit_factor = round(profit_factor, 6)

    avg_position_size = safe_div(total_volume, num_trades) if num_trades else None
    if avg_position_size is not None:
        avg_position_size = round(avg_position_size, 2)

    avg_holding_duration = None
    if holding_count > 0:
        avg_holding_duration = total_holding_seconds / holding_count

    # ── Threshold filter ───────────────────────────────────────────
    if num_trades < MIN_CATEGORY_TRADES:
        return None

    return {
        "wallet": wallet,
        "category": category,
        "snapshot_date": today,
        "num_trades": num_trades,
        "total_volume": round(total_volume, 2),
        "total_cost_basis": round(total_cost_basis, 2),
        "total_pnl": round(total_pnl, 2),
        "total_realized_pnl": round(total_realized_pnl, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "roi": roi,
        "win_rate": win_rate,
        "num_resolved_positions": resolved_total,
        "profit_factor": profit_factor,
        "avg_position_size": avg_position_size,
        "avg_holding_duration": avg_holding_duration,
        "is_specialist": False,    # will be set in post-processing
        "category_rank": None,     # will be set in post-processing
    }


@transformer
def transform_df(
    positions: DataFrame,
    trades: DataFrame,
    market_categories: DataFrame,
    *args,
    **kwargs,
) -> DataFrame:
    """Compute per-category wallet metrics.

    Args:
        positions: DataFrame from load_positions_data (with wallet, market_id, etc.)
        trades: DataFrame from load_trades_data (with wallet, market_id, etc.)
        market_categories: DataFrame from load_market_categories [market_id, category]

    Returns:
        DataFrame with columns matching the category_analytics table schema,
        plus is_specialist and category_rank set.
    """
    if market_categories.empty:
        print("No market categories available — skipping category analytics")
        return DataFrame(columns=[
            "wallet", "category", "snapshot_date", "num_trades",
            "total_volume", "total_cost_basis", "total_pnl",
            "total_realized_pnl", "total_unrealized_pnl", "roi",
            "win_rate", "num_resolved_positions", "profit_factor",
            "avg_position_size", "avg_holding_duration",
            "is_specialist", "category_rank",
        ])

    # ── Join trades with categories ────────────────────────────────
    trades_with_cat = DataFrame()
    if not trades.empty:
        trades_with_cat = trades.merge(
            market_categories, on="market_id", how="left"
        )
        before = len(trades_with_cat)
        trades_with_cat = trades_with_cat.dropna(subset=["category"])
        dropped = before - len(trades_with_cat)
        if dropped:
            print(f"Dropped {dropped} trades with NULL category")

    # ── Join positions with categories ─────────────────────────────
    positions_with_cat = DataFrame()
    if not positions.empty:
        positions_with_cat = positions.merge(
            market_categories, on="market_id", how="left"
        )
        before = len(positions_with_cat)
        positions_with_cat = positions_with_cat.dropna(subset=["category"])
        dropped = before - len(positions_with_cat)
        if dropped:
            print(f"Dropped {dropped} positions with NULL category")

    # ── Discover all (wallet, category) pairs ──────────────────────
    pairs: set[tuple[str, str]] = set()

    if not trades_with_cat.empty:
        for _, row in trades_with_cat[["wallet", "category"]].drop_duplicates().iterrows():
            pairs.add((row["wallet"], row["category"]))

    if not positions_with_cat.empty:
        for _, row in positions_with_cat[["wallet", "category"]].drop_duplicates().iterrows():
            pairs.add((row["wallet"], row["category"]))

    sorted_pairs = sorted(pairs)
    print(f"Computing category metrics for {len(sorted_pairs)} (wallet, category) pairs")

    # ── Compute per-pair metrics ───────────────────────────────────
    rows = []
    for i, (wallet, category) in enumerate(sorted_pairs, 1):
        result = compute_metrics_for_wallet_category(
            wallet, category, trades_with_cat, positions_with_cat,
        )
        if result is not None:
            rows.append(result)
        if i % 200 == 0 or i == len(sorted_pairs):
            print(f"  processed {i}/{len(sorted_pairs)} pairs")

    if not rows:
        print("No (wallet, category) pairs met the minimum threshold")
        return DataFrame(columns=[
            "wallet", "category", "snapshot_date", "num_trades",
            "total_volume", "total_cost_basis", "total_pnl",
            "total_realized_pnl", "total_unrealized_pnl", "roi",
            "win_rate", "num_resolved_positions", "profit_factor",
            "avg_position_size", "avg_holding_duration",
            "is_specialist", "category_rank",
        ])

    result_df = DataFrame(rows)
    print(f"Base metrics computed for {len(result_df)} (wallet, category) pairs")

    # ── Post-processing: specialist detection & ranking ────────────
    # Compute category-level medians for ROI and volume
    category_stats = (
        result_df
        .groupby("category")[["roi", "total_volume"]]
        .median()
        .rename(columns={"roi": "median_roi", "total_volume": "median_volume"})
        .reset_index()
    )

    result_df = result_df.merge(category_stats, on="category", how="left")

    # Mark specialists: ROI > median ROI AND volume > median volume
    result_df["is_specialist"] = (
        (result_df["roi"] > result_df["median_roi"])
        & (result_df["total_volume"] > result_df["median_volume"])
    )

    # Rank wallets within each category by ROI (descending)
    result_df["category_rank"] = (
        result_df
        .groupby("category")["roi"]
        .rank(method="dense", ascending=False)
        .astype("Int64")
    )

    # Drop helper columns
    result_df = result_df.drop(columns=["median_roi", "median_volume"])

    specialist_count = int(result_df["is_specialist"].sum())
    print(
        f"Post-processing complete: {len(result_df)} rows, "
        f"{specialist_count} specialists detected, "
        f"{result_df['category'].nunique()} categories represented"
    )

    return result_df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
    if not df.empty:
        assert "wallet" in df.columns, "Missing wallet column"
        assert "category" in df.columns, "Missing category column"
        assert "is_specialist" in df.columns, "Missing is_specialist column"
        assert "category_rank" in df.columns, "Missing category_rank column"
```

---

## 6. export_category_analytics.py (Data Exporter)

### Purpose

Four-step export:

1. **Upsert** each row from `compute_category_metrics` into `category_analytics` using `ON CONFLICT DO UPDATE`.
2. **Build top-50 rankings**: for each category, select the 50 wallets with the highest `category_rank` (i.e., best ROI).
3. **Build specialist rankings**: select all rows where `is_specialist = True`.
4. **Replace `category_rankings` for today**: DELETE existing rows for `CURRENT_DATE`, then INSERT top-50 and specialist rows.

### Design Decisions

- Uses `ON CONFLICT (wallet, category, snapshot_date) DO UPDATE` so the same pipeline can be re-run on the same day without duplicate-key errors.
- `category_rankings` uses DELETE + INSERT (not upsert) because the ranking set changes entirely each run — a wallet may fall out of the top 50, and DELETE ensures it is removed.
- The `_val` helper (converting NaN/Inf to SQL NULL) follows the exact same pattern as `export_analytics.py`.

### Column Groups

```python
CATEGORY_ANALYTICS_NUM_COLS = [
    "total_pnl", "total_realized_pnl", "total_unrealized_pnl",
    "roi", "total_volume", "total_cost_basis", "win_rate",
    "profit_factor", "avg_position_size",
]
CATEGORY_ANALYTICS_INT_COLS = ["num_trades", "num_resolved_positions", "category_rank"]
CATEGORY_ANALYTICS_STR_COLS = ["wallet", "category"]
CATEGORY_ANALYTICS_BOOL_COLS = ["is_specialist"]
```

### Code

```python
import math

from pandas import DataFrame, isna
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"

NUM_COLS = [
    "total_pnl", "total_realized_pnl", "total_unrealized_pnl",
    "roi", "total_volume", "total_cost_basis", "win_rate",
    "profit_factor", "avg_position_size",
]
INT_COLS = ["num_trades", "num_resolved_positions", "category_rank"]
STR_COLS = ["wallet", "category"]
BOOL_COLS = ["is_specialist"]


def _val(v):
    """Convert numpy NaN/Inf to SQL NULL."""
    if v is None or (not isinstance(v, str) and isna(v)):
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _bool_val(v):
    """Convert a value to a Python bool or None."""
    if v is None or (not isinstance(v, bool) and isna(v)):
        return None
    return bool(v)


@data_exporter
def export_data(df: DataFrame, **kwargs) -> None:
    if df.empty:
        print("No category analytics to export — DataFrame is empty")
        return

    today = df["snapshot_date"].iloc[0]

    print(
        f"Exporting category analytics: {len(df)} rows, "
        f"{df['category'].nunique()} categories, "
        f"snapshot_date={today}"
    )

    # ── Step 1: Upsert into category_analytics ─────────────────────
    engine = create_engine(DATABASE_URL)

    with engine.begin() as conn:
        inserted = 0
        for _, row in df.iterrows():
            params = {}
            for c in STR_COLS:
                params[c] = row.get(c)
            for c in INT_COLS:
                params[c] = _val(row.get(c))
            for c in NUM_COLS:
                params[c] = _val(row.get(c))
            for c in BOOL_COLS:
                params[c] = _bool_val(row.get(c))
            params["snapshot_date"] = row["snapshot_date"]
            params["avg_holding_duration"] = _val(row.get("avg_holding_duration"))

            conn.execute(
                text("""
                    INSERT INTO category_analytics (
                        wallet, category, snapshot_date,
                        num_trades, total_volume, total_cost_basis,
                        total_pnl, total_realized_pnl, total_unrealized_pnl,
                        roi, win_rate, num_resolved_positions,
                        profit_factor, avg_position_size, avg_holding_duration,
                        is_specialist, category_rank
                    ) VALUES (
                        :wallet, :category, :snapshot_date,
                        :num_trades, :total_volume, :total_cost_basis,
                        :total_pnl, :total_realized_pnl, :total_unrealized_pnl,
                        :roi, :win_rate, :num_resolved_positions,
                        :profit_factor, :avg_position_size, :avg_holding_duration,
                        :is_specialist, :category_rank
                    )
                    ON CONFLICT (wallet, category, snapshot_date) DO UPDATE SET
                        num_trades = EXCLUDED.num_trades,
                        total_volume = EXCLUDED.total_volume,
                        total_cost_basis = EXCLUDED.total_cost_basis,
                        total_pnl = EXCLUDED.total_pnl,
                        total_realized_pnl = EXCLUDED.total_realized_pnl,
                        total_unrealized_pnl = EXCLUDED.total_unrealized_pnl,
                        roi = EXCLUDED.roi,
                        win_rate = EXCLUDED.win_rate,
                        num_resolved_positions = EXCLUDED.num_resolved_positions,
                        profit_factor = EXCLUDED.profit_factor,
                        avg_position_size = EXCLUDED.avg_position_size,
                        avg_holding_duration = EXCLUDED.avg_holding_duration,
                        is_specialist = EXCLUDED.is_specialist,
                        category_rank = EXCLUDED.category_rank
                """),
                params,
            )
            inserted += 1

        print(f"  Step 1 complete: {inserted} rows upserted into category_analytics")

    # ── Step 2: Build top-50 per category rankings ─────────────────
    top_50_rows = (
        df[df["category_rank"].notna()]
        .sort_values(["category", "category_rank"])
        .groupby("category")
        .head(50)
        .copy()
    )
    top_50_rows["list_type"] = "top_50"

    # ── Step 3: Build specialist rankings ──────────────────────────
    specialist_rows = df[df["is_specialist"] == True].copy()  # noqa: E712
    if not specialist_rows.empty:
        specialist_rows = specialist_rows.copy()
        specialist_rows["list_type"] = "specialists"
        # Re-rank specialists across all categories by ROI
        specialist_rows = specialist_rows.sort_values("roi", ascending=False).reset_index(drop=True)
        specialist_rows["rank"] = range(1, len(specialist_rows) + 1)

    # Assign rank for top_50 rows
    if not top_50_rows.empty:
        top_50_rows["rank"] = top_50_rows.groupby("category").cumcount() + 1

    rankings = DataFrame()
    if not top_50_rows.empty:
        rankings = top_50_rows
    if not specialist_rows.empty:
        rankings = (
            DataFrame(rankings)
            if rankings.empty
            else DataFrame(rankings)._append(specialist_rows, ignore_index=True)
        )

    if rankings.empty:
        print("  No rankings to materialise — skipping Steps 2-4")
        engine.dispose()
        return

    # Ensure rank column exists (specialists already have it; top_50 does too)
    if "rank" not in rankings.columns:
        rankings["rank"] = None

    print(
        f"  Rankings to materialise: {len(top_50_rows)} top-50 rows + "
        f"{len(specialist_rows)} specialist rows = {len(rankings)} total"
    )

    # ── Step 4: Replace category_rankings for today ────────────────
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM category_rankings WHERE snapshot_date = :sd"),
            {"sd": today},
        )
        print(f"  Deleted {result.rowcount} existing category_rankings rows for {today}")

    with engine.begin() as conn:
        materialised = 0
        for _, row in rankings.iterrows():
            conn.execute(
                text("""
                    INSERT INTO category_rankings (
                        wallet, category, snapshot_date, list_type, rank,
                        roi, win_rate, total_pnl, num_trades, total_volume
                    ) VALUES (
                        :wallet, :category, :snapshot_date, :list_type, :rank,
                        :roi, :win_rate, :total_pnl, :num_trades, :total_volume
                    )
                """),
                {
                    "wallet": row["wallet"],
                    "category": row["category"],
                    "snapshot_date": today,
                    "list_type": row["list_type"],
                    "rank": int(row["rank"]) if row["rank"] is not None else None,
                    "roi": _val(row.get("roi")),
                    "win_rate": _val(row.get("win_rate")),
                    "total_pnl": _val(row.get("total_pnl")),
                    "num_trades": _val(row.get("num_trades")),
                    "total_volume": _val(row.get("total_volume")),
                },
            )
            materialised += 1

        print(f"  Step 4 complete: {materialised} rows inserted into category_rankings")

    engine.dispose()
    print("Category analytics export complete")
```

---

## 7. Orchestrator Update: run_all.py

### Changes Required

1. Add `category_analytics` to the `SLA` dictionary (120s).
2. Add `run_category_analytics()` function.
3. Add `"category_analytics"` entry to the `get_runner()` mapping.
4. Insert Phase 6 (category_analytics) after Phase 5 (enrichment_ranking_computation) and renumber existing Phase 6 → Phase 7.
5. Update SLA comment header.

### Diff (Complete Result)

Below is the **full updated file**. Lines marked `[NEW]` are additions; lines marked `[CHANGED]` are modifications to existing lines. All other lines remain as-is from the original.

```python
"""Orchestrateur ETL avec parallélisation et timeouts SLA.

Usage:
    python /home/src/scripts/run_all.py                     # Run all phases
    python /home/src/scripts/run_all.py enrichment_analytics_computation  # Single pipeline

Phases (automatique si aucun argument):
    Phase 1 — ingestion_market_discovery           (séquentiel, 120s SLA)
    Phase 2 — ingestion_wallet_discovery            (séquentiel, 120s SLA)
    Phase 3 — ingestion_position_sync + ingestion_trade_history (parallèle, 120s SLA)
    Phase 4 — enrichment_analytics_computation       (séquentiel, 60s SLA)
    Phase 5 — enrichment_ranking_computation         (séquentiel, 30s SLA)
    Phase 6 — category_analytics          (séquentiel, 120s SLA)        [NEW]
    Phase 7 — verify_etl_output           (séquentiel, 30s SLA)         [CHANGED]

Objectif SLA total: < 300s (5 minutes)
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

sys.path.insert(0, "/home/src/default_repo")

# ── Timeouts (seconds) ───────────────────────────────────────────────
SLA = {
    "ingestion_market_discovery": 120,
    "ingestion_wallet_discovery": 120,
    "ingestion_position_sync": 120,
    "ingestion_trade_history": 120,
    "enrichment_analytics_computation": 60,
    "enrichment_ranking_computation": 30,
    "category_analytics": 120,       # [NEW]
    "verify_etl_output": 30,
}
SLA_TOTAL = 300  # 5 minutes global


def elapsed() -> str:
    return f"[{time.time() - t0:.0f}s]"


def run_pipeline(name: str, fn):
    print(f"\n{'=' * 60}")
    print(f"  {elapsed()} Starting: {name}")
    print(f"{'=' * 60}")
    t_start = time.time()
    try:
        fn()
        duration = time.time() - t_start
        limit = SLA.get(name, 120)
        status = "✓" if duration <= limit else "⚠"
        print(f"  {elapsed()} {status} {name} done in {duration:.1f}s (SLA: {limit}s)")
    except Exception as e:
        duration = time.time() - t_start
        print(f"  {elapsed()} ✗ {name} FAILED after {duration:.1f}s: {e}")
        raise


def get_runner(phase: str):
    """Retourne la fonction runner correspondant au nom de pipeline."""
    runners = {
        "ingestion_market_discovery": run_market_discovery,
        "ingestion_wallet_discovery": run_wallet_discovery,
        "ingestion_position_sync": run_position_sync,
        "ingestion_trade_history": run_trade_history,
        "enrichment_analytics_computation": run_analytics,
        "enrichment_ranking_computation": run_ranking,
        "category_analytics": run_category_analytics,   # [NEW]
        "verify_etl_output": run_verification,
    }
    return runners[phase]


# ── Pipeline runners ─────────────────────────────────────────────────

def run_market_discovery():
    from data_loaders.load_active_markets import load_data_from_api as load_active
    from data_loaders.load_resolved_markets import load_data_from_api as load_resolved
    from transformers.merge_markets import transform_df
    from data_exporters.export_markets import export_data

    active = load_active()
    resolved = load_resolved()
    merged = transform_df(active, resolved)
    export_data(merged)


def run_wallet_discovery():
    from data_loaders.load_holders_for_active_markets import load_data_from_api as load_holders
    from data_loaders.resolve_proxy_wallets import load_data_from_api as resolve_proxies
    from transformers.build_wallet_records import transform_df
    from data_exporters.export_wallets import export_data

    holders = load_holders()
    resolved = resolve_proxies(holders)
    records = transform_df(holders, resolved)
    export_data(records)


def run_position_sync():
    from data_loaders.load_tracked_wallets import load_data_from_api as load_wallets
    from data_loaders.load_positions import load_data_from_api as load_positions
    from transformers.merge_positions import transform_df
    from data_exporters.export_positions import export_data

    wallets = load_wallets()
    positions = load_positions(wallets)
    merged = transform_df(positions)
    export_data(merged)


def run_trade_history():
    from data_loaders.load_tracked_wallets_for_trades import load_data_from_api as load_wallets
    from data_loaders.load_trades_for_wallet import load_data_from_api as load_trades
    from transformers.deduplicate_trades import transform_df
    from data_exporters.export_trades import export_data

    wallets = load_wallets()
    trades = load_trades(wallets)
    deduped = transform_df(trades)
    export_data(deduped)


def run_analytics():
    from data_loaders.load_recent_activity import load_data_from_api as load_recent
    from data_loaders.load_positions_data import load_data_from_api as load_positions
    from data_loaders.load_trades_data import load_data_from_api as load_trades
    from transformers.compute_wallet_metrics import transform_df
    from data_exporters.export_analytics import export_data

    wallets = load_recent()
    positions = load_positions(wallets)
    trades = load_trades(wallets)
    metrics = transform_df(positions, trades)
    export_data(metrics)


def run_ranking():
    from data_loaders.load_all_analytics import load_data_from_api as load_analytics
    from data_loaders.load_wallet_metadata import load_data_from_api as load_metadata
    from transformers.filter_eligible_wallets import transform_df as filter_eligible
    from transformers.compute_wallet_scores import transform_df as compute_scores
    from data_exporters.materialize_rankings import export_data

    analytics = load_analytics()
    metadata = load_metadata()
    eligible = filter_eligible(analytics, metadata)
    rankings = compute_scores(eligible)
    export_data(rankings)


def run_category_analytics():                                           # [NEW]
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


def run_verification():
    from data_loaders.verify_etl_output import load_data_from_api as verify

    verify()


# ── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    t0 = time.time()

    selected = sys.argv[1:]
    if selected:
        # Mode single-pipeline
        for name in selected:
            runner = get_runner(name)
            run_pipeline(name, runner)
        sys.exit(0)

    # ── Mode orchestrateur complet ───────────────────────────────────
    print(f"=== Polymarket ETL Orchestrator ===")
    print(f"SLA global: {SLA_TOTAL}s")

    # Phase 1: ingestion_market_discovery
    run_pipeline("ingestion_market_discovery", run_market_discovery)

    # Phase 2: ingestion_wallet_discovery
    run_pipeline("ingestion_wallet_discovery", run_wallet_discovery)

    # Phase 3: ingestion_position_sync + ingestion_trade_history en parallèle
    print(f"\n  {elapsed()} Phase 3: ingestion_position_sync + ingestion_trade_history (parallèle)")
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_map = {
            pool.submit(run_pipeline, "ingestion_position_sync", run_position_sync): "ingestion_position_sync",
            pool.submit(run_pipeline, "ingestion_trade_history", run_trade_history): "ingestion_trade_history",
        }
        for fut in as_completed(fut_map):
            fut.result()

    # Phase 4: enrichment_analytics_computation
    run_pipeline("enrichment_analytics_computation", run_analytics)

    # Phase 5: enrichment_ranking_computation
    run_pipeline("enrichment_ranking_computation", run_ranking)

    # Phase 6: category_analytics (NEW)                                 # [NEW]
    run_pipeline("category_analytics", run_category_analytics)          # [NEW]

    # Phase 7: verification (renumbered from Phase 6)                   # [CHANGED]
    run_pipeline("verify_etl_output", run_verification)

    # Bilan SLA global
    total = time.time() - t0
    status = "✓" if total <= SLA_TOTAL else "⚠"
    print(f"\n{'=' * 60}")
    print(f"  {status} ETL cycle completed in {total:.1f}s (SLA: {SLA_TOTAL}s)")
    print(f"{'=' * 60}")

    if total > SLA_TOTAL:
        sys.exit(1)
```

### SLA Budget Breakdown

| Phase | Pipeline | SLA (s) | Type |
|---|---|---|---|
| 1 | ingestion_market_discovery | 120 | Sequential |
| 2 | ingestion_wallet_discovery | 120 | Sequential |
| 3 | ingestion_position_sync | 120 | Parallel |
| 3 | ingestion_trade_history | 120 | Parallel |
| 4 | enrichment_analytics_computation | 60 | Sequential |
| 5 | enrichment_ranking_computation | 30 | Sequential |
| **6** | **category_analytics** | **120** | **Sequential** |
| 7 | verify_etl_output | 30 | Sequential |
| **Total** | | **≤ 300** | |

**Rationale for 120s SLA**: Category analytics processes the same volume of trades and positions as `enrichment_analytics_computation`, but must iterate over more groups (each wallet appears once per category, not once total). The 120s budget accounts for the additional grouping overhead.

---

## 8. Prerequisites & Dependencies

### 8.1 Database Schema

The following must exist **before** the pipeline runs:

1. **`markets.mapped_category`** column — added by migration `002_category_analytics`. If this column does not exist, `load_market_categories.py` will fail with a `psycopg2.errors.UndefinedColumn` error. This is intentional: the pipeline cannot function without category mappings.

2. **`category_analytics`** table — created by migration `002_category_analytics` with the schema:
   - `wallet` (Text, PK, FK → wallets.wallet)
   - `category` (Text, PK)
   - `snapshot_date` (Date, PK)
   - `num_trades` (Integer)
   - `total_volume` (Numeric(28,2))
   - `total_cost_basis` (Numeric(28,2))
   - `total_pnl` (Numeric(28,2))
   - `total_realized_pnl` (Numeric(28,2))
   - `total_unrealized_pnl` (Numeric(28,2))
   - `roi` (Numeric(8,6))
   - `win_rate` (Numeric(8,6))
   - `num_resolved_positions` (Integer)
   - `profit_factor` (Numeric(28,6))
   - `avg_position_size` (Numeric(28,2))
   - `avg_holding_duration` (Interval)
   - `is_specialist` (Boolean)
   - `category_rank` (Integer)
   - Index: `(snapshot_date, category, category_rank)`
   - Index: `(wallet, snapshot_date)`
   - FK: `wallet → wallets.wallet`

3. **`category_rankings`** table — created by migration `002_category_analytics` with the schema:
   - `wallet` (Text, PK, FK → wallets.wallet)
   - `category` (Text, PK)
   - `snapshot_date` (Date, PK)
   - `list_type` (Text, PK)
   - `rank` (Integer)
   - `roi` (Numeric(8,6))
   - `win_rate` (Numeric(8,6))
   - `total_pnl` (Numeric(28,2))
   - `num_trades` (Integer)
   - `total_volume` (Numeric(28,2))
   - Index: `(snapshot_date, category, list_type, rank)`
   - FK: `wallet → wallets.wallet`

### 8.2 Upstream Pipelines

The `category_analytics` pipeline assumes:

- **Phase 1 (ingestion_market_discovery)** has run at least once to populate `markets` with `mapped_category` values. Without this, `load_market_categories` returns an empty DataFrame and the transformer produces no output.
- **Phase 3 (ingestion_position_sync + ingestion_trade_history)** has run to populate `trades` and `positions` tables.
- **Phase 2 (ingestion_wallet_discovery)** has run to populate `wallets`, which is a FK target. However, the pipeline does not directly query `wallets` — the FK constraint on `category_analytics.wallet` requires parent rows to exist.

### 8.3 Import Note

The transformer imports `safe_div` from `transformers.compute_wallet_metrics`. This import works from within the Mage AI execution context because `sys.path` includes `/home/src/default_repo` (configured in `run_all.py`). When running via Mage's block executor, the import path is resolved by Mage's module resolution.

---

## 9. Backfill & Historical Data

### 9.1 First Run

The first time `category_analytics` runs, there is no historical data in `category_analytics` or `category_rankings`. The pipeline handles this naturally:

- `load_recent_wallets` returns wallets with trades in the last 24h.
- If no wallets have recent activity (e.g., on a brand-new deployment where Phase 3 was just seeded), the pipeline produces no rows — this is correct behaviour.
- `export_category_analytics` checks for an empty DataFrame and exits early.

### 9.2 Historical Backfill

To populate category analytics for all tracked wallets (not just recently active ones), run the pipeline with a custom SQL query for `load_recent_wallets`:

**Option A: Replace the loader query temporarily**

Replace `load_recent_activity.py`'s query with:

```sql
SELECT DISTINCT wallet FROM trades
```

Then run:
```bash
docker compose exec mage python /home/src/scripts/run_all.py category_analytics
```

Restore the original query afterwards.

**Option B: Direct SQL materialisation**

For a one-time full backfill without running the pipeline, execute:

```sql
INSERT INTO category_analytics (wallet, category, snapshot_date, ...)
SELECT ... FROM trades t
JOIN markets m ON t.market_id = m.id
WHERE m.mapped_category IS NOT NULL
GROUP BY t.wallet, m.mapped_category, CURRENT_DATE
HAVING COUNT(*) >= 30;
```

However, this SQL-only approach misses specialist detection and ranking. **Recommendation**: use Option A, then re-run `export_category_analytics` against the full backfilled data.

### 9.3 Repeated Runs on the Same Day

The pipeline uses `ON CONFLICT DO UPDATE` for `category_analytics`, so re-running on the same day overwrites previous values. The `category_rankings` table uses DELETE + INSERT, so rankings are fully replaced.

This means the pipeline is **idempotent** — running it multiple times on the same day produces the same final state (assuming the underlying trades/positions data hasn't changed).

---

## 10. Error Handling & Edge Cases

### 10.1 Empty Input DataFrames

| Scenario | Behaviour |
|---|---|
| `load_market_categories` returns empty | Transformer prints warning, returns empty DataFrame. Exporter exits early. |
| `load_positions_data` returns empty | Transformer proceeds with trades only. No position-derived metrics (realized/unrealized PnL, win_rate, profit_factor, avg_holding_duration will be NULL). |
| `load_trades_data` returns empty | Transformer proceeds with positions only. Trade-derived metrics (num_trades, total_volume, total_cost_basis) will be 0; `compute_metrics_for_wallet_category` returns None due to < 30 trade threshold. Result: no rows. |
| Both trades and positions empty | Transformer returns empty DataFrame. Exporter exits early. |

### 10.2 NULL / Missing Data

| Scenario | Behaviour |
|---|---|
| `mapped_category` is NULL for a market | Market is excluded from category analytics. Trade/position using this market is dropped at the join step. |
| `price` or `shares` is NULL in a trade row | `to_numeric(..., errors="coerce").fillna(0)` converts it to 0. |
| `entry_time` or `exit_time` is NULL in a position | Holding duration is skipped for that position (does not contribute to avg). |
| `realized_pnl` has NaN | Filled to 0; does not affect win/loss classification (0 is not > 0). |

### 10.3 Edge Cases

| Scenario | Behaviour |
|---|---|
| Wallet has 50 trades but only 5 in one category | Not included for that category (< 30 threshold). Still present in global analytics. |
| All wallets have `is_specialist = False` | Specialist rankings list will be empty (exporter logs a message). Top-50 rankings are still materialised. |
| Only 1 category has enough traders | Only that category appears in `category_rankings`. Other categories with < 50 wallets get partial top-50 lists. |
| ROI is infinite (total_pnl > 0, total_cost_basis = 0) | `safe_div` returns None. ROI is stored as NULL. Wallet is not eligible for specialist status (NULL ROI is not > median). |
| A wallet appears in trades but not in positions | All position-derived metrics are 0/NULL. Wallet can still qualify if trade count ≥ 30 and volume ≥ $1000. |
| Duplicate wallet rows for same (category, date) | ON CONFLICT DO UPDATE ensures the last-updated value wins. No duplicate PK errors. |

### 10.4 Pipeline Failures

- If **any loader fails** (DB connection error, missing table), the entire pipeline fails. The orchestrator catches the exception and reports it with the pipeline name and duration.
- If the **transformer runs out of memory** (too many (wallet, category) pairs), the pipeline fails. Mitigation: the `load_recent_wallets` loader limits wallets to those active in the last 24h, which bounds the input size.
- If the **exporter's DELETE** succeeds but the **INSERT** fails (e.g., FK violation), the `category_rankings` for today is partially empty. Mitigation: the DELETE and INSERT run in separate transactions (two `engine.begin()` blocks). A re-run will DELETE again (safe on an already-cleaned table) and retry the INSERT.

### 10.5 JSON Serialisability

All DataFrames and their contents must be JSON-serialisable for Mage's block output cache. The following types are used:

- `str`, `int`, `float`, `bool` — all JSON-safe.
- `date` — converted to string by Mage's serialiser.
- `None` — serialised as `null`.
- `NaT` / `NaN` — converted to `None` by `_val()` in the exporter.

The transformer returns a plain `DataFrame` (not a dict), which Mage handles natively.

---

## 11. Acceptance Criteria

### 11.1 Functional

- [ ] Pipeline runs end-to-end with no errors via `run_all.py category_analytics`
- [ ] Pipeline runs as Phase 6 of the full orchestrator (all 7 phases complete)
- [ ] `category_analytics` table populated with rows for at least 3 categories
- [ ] `category_rankings` table populated with top-50 per category + specialist rows
- [ ] At least 100 (wallet, category) pairs across all categories
- [ ] No duplicate (wallet, category, snapshot_date) rows in `category_analytics`
- [ ] No duplicate (wallet, category, snapshot_date, list_type) rows in `category_rankings`
- [ ] `roi` values within [-100, 10000] range
- [ ] `win_rate` values within [0, 1]
- [ ] `is_specialist` is True for ≤ 50% of rows in each category (by definition: above median)
- [ ] `category_rank` values are sequential (1, 2, 3, ...) within each category
- [ ] Pipeline completes within 120s SLA

### 11.2 Data Integrity

- [ ] All `category_analytics.wallet` values exist in `wallets.wallet`
- [ ] All `category_analytics.category` values match one of the 8 target categories
- [ ] Re-running the pipeline on the same day does not change row counts (idempotent)
- [ ] Existing Phase 1 tables (`wallet_analytics`, `ranking_snapshots`) are untouched
- [ ] Existing 6 pipelines still run correctly after the addition

### 11.3 Code Quality

- [ ] No duplicated metric computation logic (all reuse of `safe_div` from `compute_wallet_metrics`)
- [ ] All 6 new files created (pipeline dir, metadata, loader, transformer, exporter, trigger)
- [ ] Orchestrator updated with correct SLA and phase ordering
- [ ] No hardcoded values except `MIN_CATEGORY_TRADES = 30` and `DATABASE_URL`
- [ ] All `@test` decorators pass

---

## Appendix A: File Manifest

```
# New files to create:
magic/default_repo/pipelines/category_analytics/__init__.py
magic/default_repo/pipelines/category_analytics/metadata.yaml
magic/default_repo/pipelines/category_analytics/triggers/default.yaml
magic/default_repo/data_loaders/load_market_categories.py
magic/default_repo/transformers/compute_category_metrics.py
magic/default_repo/data_exporters/export_category_analytics.py

# Existing files to modify:
magic/scripts/run_all.py                           # Add Phase 6
```

## Appendix B: Table Schemas (for Reference)

### `category_analytics`

```sql
CREATE TABLE category_analytics (
    wallet              TEXT NOT NULL REFERENCES wallets(wallet),
    category            TEXT NOT NULL,
    snapshot_date       DATE NOT NULL,
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
    is_specialist       BOOLEAN,
    category_rank       INTEGER,
    PRIMARY KEY (wallet, category, snapshot_date)
);

CREATE INDEX idx_cat_analytics_leaderboard
    ON category_analytics (snapshot_date, category, category_rank);

CREATE INDEX idx_cat_analytics_wallet
    ON category_analytics (wallet, snapshot_date);
```

### `category_rankings`

```sql
CREATE TABLE category_rankings (
    wallet          TEXT NOT NULL REFERENCES wallets(wallet),
    category        TEXT NOT NULL,
    snapshot_date   DATE NOT NULL,
    list_type       TEXT NOT NULL,
    rank            INTEGER NOT NULL,
    roi             NUMERIC(8, 6),
    win_rate        NUMERIC(8, 6),
    total_pnl       NUMERIC(28, 2),
    num_trades      INTEGER,
    total_volume    NUMERIC(28, 2),
    PRIMARY KEY (wallet, category, snapshot_date, list_type)
);

CREATE INDEX idx_cat_rankings_leaderboard
    ON category_rankings (snapshot_date, category, list_type, rank);
```

## Appendix C: Quick Start for Implementing

1. **Prerequisites**: Ensure migration `002_category_analytics` is applied (`alembic upgrade head`).
2. **Create pipeline files** (6 new files from File Manifest above).
3. **Update orchestrator** (`run_all.py` — see Section 7).
4. **Restart Mage** (or reload pipelines via Mage UI).
5. **Run pipeline**:
   ```bash
   docker compose exec mage python /home/src/scripts/run_all.py category_analytics
   ```
6. **Verify output**:
   ```bash
   docker compose exec postgres psql -U app -d polymarket -c \
     "SELECT category, COUNT(*) AS rows, COUNT(DISTINCT wallet) AS wallets FROM category_analytics GROUP BY category ORDER BY rows DESC;"
   docker compose exec postgres psql -U app -d polymarket -c \
     "SELECT list_type, category, COUNT(*) FROM category_rankings GROUP BY list_type, category ORDER BY list_type, category;"
   ```
7. **Run full orchestrator** to confirm no regression:
   ```bash
   docker compose exec mage python /home/src/scripts/run_all.py
   ```
