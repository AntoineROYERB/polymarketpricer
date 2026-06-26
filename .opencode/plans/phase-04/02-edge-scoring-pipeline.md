# Phase 4 — Edge Scoring — ETL Pipeline

> **Goal**: Compute edge (ROI per trade) for every trade on a resolved market, aggregate into per-wallet daily snapshots, and store in `wallet_edge_snapshots`.
> **AI Agent Instructions**: Create a new Mage AI pipeline `enrichment_edge_scoring` with data loaders, transformer, data exporter, and register it in the orchestration pipeline between `category_analytics` and `enrichment_ranking_computation`.

---

## Pipeline: `enrichment_edge_scoring`

### Position in Pipeline Order

```
enrichment_category_analytics (upstream)
         │
         ▼
enrichment_edge_scoring  ◄── NEW — after category_analytics, before ranking_computation
         │
         ▼
enrichment_ranking_computation (downstream — updated to read edge_score)
```

### Data Flow

```
         trades table (resolved markets only)
         markets table (JOIN for resolution status + winner)
         outcomes table (JOIN for resolution_price)
                │
                ▼
   load_resolved_trades.py
   (PG query: trades on markets WHERE
    markets.resolved = true,
    LEFT JOIN outcomes.winner)
                │
                ▼
   load_trade_outcomes.py
   (PG query: outcomes for resolution_price)
                │
                ▼
   compute_trade_edge.py
   (transformer — implements edge algorithm:
    link BUY → SELL pairs via FIFO,
    compute edge per trade,
    aggregate per wallet)
                │
                ▼
   export_edge_snapshots.py
   (UPSERT into wallet_edge_snapshots)
```

### File Manifest

```
magic/default_repo/pipelines/enrichment_edge_scoring/
├── __init__.py              (empty)
├── metadata.yaml            (pipeline definition)
└── triggers/                (empty directory)

magic/default_repo/data_loaders/load_resolved_trades.py
magic/default_repo/data_loaders/load_trade_outcomes.py
magic/default_repo/transformers/compute_trade_edge.py
magic/default_repo/data_exporters/export_edge_snapshots.py
magic/default_repo/data_exporters/trigger_edge_scoring.py
```

---

## 1. Data Loader: `load_resolved_trades.py`

Loads all trades on resolved markets with market metadata. This is the base dataset for edge computation.

```python
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"

TRADES_QUERY = """
SELECT
    t.id AS trade_id,
    t.wallet,
    t.market_id,
    t.outcome_id,
    t.type,            -- 'BUY' or 'SELL'
    t.price,
    t.size,
    t.amount_usd,
    t.shares,
    t.created_at,
    m.question AS market_question,
    m.resolution,
    m.resolution_source,
    o.outcome AS outcome_label,
    o.winner AS outcome_winner
FROM trades t
JOIN markets m ON m.id = t.market_id
LEFT JOIN outcomes o ON o.id = t.outcome_id
WHERE m.resolved = true
  AND t.created_at >= '2024-01-01'  -- reasonable lower bound
ORDER BY t.wallet, t.market_id, t.outcome_id, t.created_at ASC
"""


@data_loader
def load_data(*args, **kwargs) -> DataFrame:
    """Load all trades on resolved markets, ordered chronologically per wallet."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        rows = conn.execute(text(TRADES_QUERY)).mappings().all()

    engine.dispose()

    if not rows:
        print("No resolved trades found — returning empty DataFrame")
        return DataFrame(columns=[
            "trade_id", "wallet", "market_id", "outcome_id", "type",
            "price", "size", "amount_usd", "shares", "created_at",
            "market_question", "resolution", "resolution_source",
            "outcome_label", "outcome_winner",
        ])

    df = DataFrame(rows)
    print(f"Loaded {len(df)} trades on resolved markets")
    return df


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert "wallet" in df.columns
        assert "market_id" in df.columns
        assert "type" in df.columns
        assert "price" in df.columns
```

---

## 2. Data Loader: `load_trade_outcomes.py`

Loads outcomes for resolution price computation.

```python
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"

OUTCOMES_QUERY = """
SELECT
    o.id AS outcome_id,
    o.market_id,
    o.outcome,
    o.winner
FROM outcomes o
JOIN markets m ON m.id = o.market_id
WHERE m.resolved = true
"""


@data_loader
def load_data(*args, **kwargs) -> DataFrame:
    """Load all outcomes for resolved markets (resolution price mapping)."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        rows = conn.execute(text(OUTCOMES_QUERY)).mappings().all()

    engine.dispose()

    if not rows:
        print("No resolved outcomes found — returning empty DataFrame")
        return DataFrame(columns=["outcome_id", "market_id", "outcome", "winner"])

    df = DataFrame(rows)
    print(f"Loaded {len(df)} outcomes for resolved markets")
    return df


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert "market_id" in df.columns
        assert "winner" in df.columns
```

---

## 3. Transformer: `compute_trade_edge.py`

Core edge computation logic. Implements the algorithm defined in the Phase 4 specification.

### Algorithm (from spec)

```python
# Pour chaque trade sur un marché résolu :
# 1. Si c'est un BUY :
#    - Chercher si ce wallet a un SELL ultérieur pour le même market+outcome
#    - Si oui : edge_price = sell_price du SELL associé (FIFO)
#    - Si non : edge_price = resolution_price (1.0 ou 0.0)
# 2. Si c'est un SELL :
#    - Ignorer (l'edge est attribué au BUY correspondant)
#    - Sauf si pas de BUY trouvé → ignorer le trade
# 3. edge = (edge_price - entry_price) / entry_price
# 4. Edge > 0 → positif pour edge_consistency
# 5. Edge = 0 → compté comme négatif dans edge_consistency
```

### Notes on edge_price

- **edge_price** = resolution price (1.0 for winning token, 0.0 for losing) if held to resolution, **OR** sell_price if sold before resolution.
- **Consensus** = resolution outcome (winner = 1.0, loser = 0.0).
- **SELL with no identifiable BUY** (e.g. tokens obtained via REDEEM/MERGE/SPLIT): skip the trade entirely (no entry_price → no edge computable).
- **Multiple BUY on same wallet+market+outcome**: edge computed PER TRADE individually (FIFO matching to SELLs).
- **`edge_score`** = `avg_edge` normalised to [0, 1] via min-max scaling across all wallets in the batch.

### Transformer Implementation

```python
from decimal import Decimal, ROUND_HALF_UP
from statistics import median, stdev
from pandas import DataFrame, to_numeric

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

# Resolution price mapping — winner = 1.0, loser = 0.0
RESOLUTION_PRICE_WINNER = Decimal("1.0")
RESOLUTION_PRICE_LOSER = Decimal("0.0")


def resolve_price(outcome_winner: bool | None) -> Decimal:
    """Return resolution price for an outcome."""
    if outcome_winner is True:
        return RESOLUTION_PRICE_WINNER
    return RESOLUTION_PRICE_LOSER


def compute_wallet_edge(trades: DataFrame, outcomes: DataFrame) -> list[dict]:
    """Compute edge per trade for a single wallet on resolved markets.

    Uses FIFO matching: the oldest unmatched BUY is matched to the oldest SELL
    on the same (market_id, outcome_id).

    Returns a list of edge dicts per matched BUY trade.
    """
    from collections import defaultdict, deque

    # Build resolution_price lookup: (market_id) -> (outcome_id -> price)
    resolution_prices: dict[str, dict[str, Decimal]] = {}
    for _, row in outcomes.iterrows():
        market_id = str(row["market_id"])
        outcome_id = str(row["outcome_id"])
        winner = row.get("winner")
        if market_id not in resolution_prices:
            resolution_prices[market_id] = {}
        resolution_prices[market_id][outcome_id] = resolve_price(winner)

    # Group trades by (wallet, market_id, outcome_id)
    groups: dict[tuple[str, str, str], deque] = defaultdict(deque)
    for _, row in trades.iterrows():
        key = (str(row["wallet"]), str(row["market_id"]), str(row["outcome_id"]))
        groups[key].append(row.to_dict())

    edge_results: list[dict] = []

    for (wallet, market_id, outcome_id), trade_list in groups.items():
        # FIFO matching: BUY queue, SELL queue
        buy_queue: deque = deque()
        sell_queue: deque = deque()

        for trade in trade_list:
            ttype = str(trade.get("type", "")).strip().upper()
            if ttype == "BUY":
                buy_queue.append(trade)
            elif ttype == "SELL":
                sell_queue.append(trade)

        # Match each BUY to a SELL (FIFO) or resolution
        while buy_queue:
            buy = buy_queue.popleft()
            entry_price = Decimal(str(buy.get("price", 0)))
            size = Decimal(str(buy.get("size", 0)))

            # Skip trades with zero entry price (can't compute edge)
            if entry_price <= 0:
                continue

            # Try to match with a SELL
            edge_price: Decimal | None = None
            matched_sell = None

            if sell_queue:
                matched_sell = sell_queue.popleft()
                edge_price = Decimal(str(matched_sell.get("price", 0)))
            else:
                # No sell: use resolution price
                market_prices = resolution_prices.get(market_id, {})
                edge_price = market_prices.get(outcome_id)

            if edge_price is None:
                # No resolution price available — can't compute edge
                continue

            # Compute edge per trade: (edge_price - entry_price) / entry_price
            edge = (edge_price - entry_price) / entry_price

            edge_results.append({
                "wallet": wallet,
                "market_id": market_id,
                "outcome_id": outcome_id,
                "trade_id": str(buy.get("trade_id", "")),
                "entry_price": entry_price,
                "edge_price": edge_price,
                "edge": edge,
                "size": size,
                "is_positive": edge > 0,
                "had_sell": matched_sell is not None,
            })

            # If the SELL consumed only part of the BUY's shares,
            # we would need partial matching. For MVP, we assume
            # one SELL fully closes the position. Partial matching
            # is deferred to post-MVP refinement.

        # Any remaining unmatched SELLs are ignored (edge attributed to BUY side)

    return edge_results


@transformer
def compute_edges(trades_df: DataFrame, outcomes_df: DataFrame, *args, **kwargs) -> DataFrame:
    """Compute edge for all trades on resolved markets and aggregate per wallet."""
    if trades_df.empty:
        print("No trades to process — returning empty DataFrame")
        return DataFrame(columns=[
            "wallet", "snapshot_date", "avg_edge", "median_edge",
            "edge_consistency", "edge_volatility", "edge_score",
            "num_edge_trades", "positive_edge_trades", "negative_edge_trades",
        ])

    # Cast numeric columns safely
    for col in ["price", "size", "amount_usd", "shares"]:
        if col in trades_df.columns:
            trades_df[col] = to_numeric(trades_df[col], errors="coerce").fillna(0)

    # Ensure created_at is datetime
    trades_df["created_at"] = trades_df["created_at"].astype("datetime64[ns]")

    # Compute per-trade edges
    edge_records = compute_wallet_edge(trades_df, outcomes_df)

    if not edge_records:
        print("No computable edges — returning empty DataFrame")
        return DataFrame(columns=[
            "wallet", "snapshot_date", "avg_edge", "median_edge",
            "edge_consistency", "edge_volatility", "edge_score",
            "num_edge_trades", "positive_edge_trades", "negative_edge_trades",
        ])

    # Aggregate per wallet
    from datetime import date
    from statistics import median as stat_median, stdev as stat_stdev

    wallet_edges: dict[str, list[Decimal]] = {}
    wallet_positives: dict[str, int] = {}
    wallet_negatives: dict[str, int] = {}

    for rec in edge_records:
        w = rec["wallet"]
        if w not in wallet_edges:
            wallet_edges[w] = []
            wallet_positives[w] = 0
            wallet_negatives[w] = 0
        wallet_edges[w].append(rec["edge"])
        if rec["is_positive"]:
            wallet_positives[w] += 1
        else:
            wallet_negatives[w] += 1

    snapshot_date = date.today()
    snapshot_rows = []

    all_edge_values = []
    for edges in wallet_edges.values():
        all_edge_values.extend([float(e) for e in edges])

    if all_edge_values:
        min_edge = min(all_edge_values)
        max_edge = max(all_edge_values)
        edge_range = max_edge - min_edge if max_edge != min_edge else 1.0
    else:
        min_edge = 0.0
        edge_range = 1.0

    for wallet, edges in wallet_edges.items():
        float_edges = [float(e) for e in edges]
        avg_edge = sum(float_edges) / len(float_edges)
        med_edge = stat_median(float_edges) if len(float_edges) > 1 else float_edges[0]
        vol = stat_stdev(float_edges) if len(float_edges) > 1 else 0.0
        consistency = wallet_positives[wallet] / len(float_edges)
        # Edge score = min-max normalisation of avg_edge into [0, 1]
        edge_score = (avg_edge - min_edge) / edge_range

        snapshot_rows.append({
            "wallet": wallet,
            "snapshot_date": snapshot_date,
            "avg_edge": avg_edge,
            "median_edge": med_edge,
            "edge_consistency": consistency,
            "edge_volatility": vol,
            "edge_score": edge_score,
            "num_edge_trades": len(float_edges),
            "positive_edge_trades": wallet_positives[wallet],
            "negative_edge_trades": wallet_negatives[wallet],
        })

    result = DataFrame(snapshot_rows)
    print(f"Computed edge snapshots for {len(result)} wallets "
          f"(from {len(edge_records)} trade edges)")
    return result


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert "wallet" in df.columns
        assert "avg_edge" in df.columns
        assert "edge_score" in df.columns
        assert "num_edge_trades" in df.columns
        assert df["edge_score"].between(0, 1, inclusive="both").all(), \
            "edge_score must be in [0, 1]"
        assert df["avg_edge"].notna().all(), "avg_edge must not be NULL"
        assert df["num_edge_trades"].ge(1).all(), \
            "Each wallet must have at least 1 edge trade"
```

---

## 4. Data Exporter: `export_edge_snapshots.py`

UPSERT aggregated edge snapshots into `wallet_edge_snapshots`.

```python
from datetime import date
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"

UPSERT_SQL = """
INSERT INTO wallet_edge_snapshots (
    wallet, snapshot_date, avg_edge, median_edge,
    edge_consistency, edge_volatility, edge_score,
    num_edge_trades, positive_edge_trades, negative_edge_trades,
    computed_at
)
VALUES (
    :wallet, :snapshot_date, :avg_edge, :median_edge,
    :edge_consistency, :edge_volatility, :edge_score,
    :num_edge_trades, :positive_edge_trades, :negative_edge_trades,
    NOW()
)
ON CONFLICT (wallet, snapshot_date)
DO UPDATE SET
    avg_edge = EXCLUDED.avg_edge,
    median_edge = EXCLUDED.median_edge,
    edge_consistency = EXCLUDED.edge_consistency,
    edge_volatility = EXCLUDED.edge_volatility,
    edge_score = EXCLUDED.edge_score,
    num_edge_trades = EXCLUDED.num_edge_trades,
    positive_edge_trades = EXCLUDED.positive_edge_trades,
    negative_edge_trades = EXCLUDED.negative_edge_trades,
    computed_at = NOW()
"""


@data_exporter
def export_data(snapshots: DataFrame, **kwargs) -> None:
    """UPSERT edge snapshots into wallet_edge_snapshots."""
    if snapshots.empty:
        print("No edge snapshots to export")
        return

    engine = create_engine(DATABASE_URL)

    with engine.begin() as conn:
        for _, row in snapshots.iterrows():
            conn.execute(text(UPSERT_SQL), {
                "wallet": str(row["wallet"]),
                "snapshot_date": row.get("snapshot_date", date.today()),
                "avg_edge": float(row["avg_edge"]),
                "median_edge": float(row.get("median_edge", 0)),
                "edge_consistency": float(row.get("edge_consistency", 0)),
                "edge_volatility": float(row.get("edge_volatility", 0)),
                "edge_score": float(row.get("edge_score", 0)),
                "num_edge_trades": int(row["num_edge_trades"]),
                "positive_edge_trades": int(row.get("positive_edge_trades", 0)),
                "negative_edge_trades": int(row.get("negative_edge_trades", 0)),
            })

    engine.dispose()
    print(f"Exported {len(snapshots)} edge snapshots")


@test
def test_output(*args) -> None:
    pass
```

---

## 5. Pipeline Metadata

Create `magic/default_repo/pipelines/enrichment_edge_scoring/metadata.yaml`:

```yaml
blocks:
- all_upstream_blocks_executed: true
  color: null
  configuration: {}
  downstream_blocks:
  - load_resolved_trades
  - load_trade_outcomes
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: load_resolved_trades
  retry_config: null
  status: not_executed
  timeout: null
  type: data_loader
  upstream_blocks: []
  uuid: load_resolved_trades
- all_upstream_blocks_executed: true
  color: null
  configuration: {}
  downstream_blocks:
  - load_resolved_trades
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: load_trade_outcomes
  retry_config: null
  status: not_executed
  timeout: null
  type: data_loader
  upstream_blocks: []
  uuid: load_trade_outcomes
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks:
  - compute_trade_edge
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: compute_trade_edge
  retry_config: null
  status: not_executed
  timeout: null
  type: transformer
  upstream_blocks:
  - load_resolved_trades
  - load_trade_outcomes
  uuid: compute_trade_edge
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks: []
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: export_edge_snapshots
  retry_config: null
  status: not_executed
  timeout: null
  type: data_exporter
  upstream_blocks:
  - compute_trade_edge
  uuid: export_edge_snapshots
cache_block_output_in_memory: false
callbacks: []
concurrency_config: {}
conditionals: []
created_at: null
data_integration: null
description: "Compute edge (ROI per trade) on resolved markets and aggregate per wallet"
executor_config: {}
executor_count: 1
executor_type: null
extensions: {}
name: enrichment_edge_scoring
notification_config: {}
remote_variables_dir: null
retry_config: {}
run_pipeline_in_one_process: false
settings:
  triggers: null
spark_config: {}
tags: []
type: python
uuid: enrichment_edge_scoring
variables_dir: /home/src/mage_data/default_repo
widgets: []
```

---

## 6. Orchestration Registration

### Create trigger block

Create `magic/default_repo/data_exporters/trigger_edge_scoring.py`:

```python
if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline


@data_exporter
def export_data(**kwargs) -> None:
    trigger_pipeline(
        'enrichment_edge_scoring',
        variables={},
        check_status=False,
        error_on_failure=True,
        poll_interval=30,
        poll_timeout=300,       # 5 min — edge scoring may be intensive
        schedule_name=None,
        verbose=True,
    )
```

### Edit orchestration metadata

Add this block at the end of `magic/default_repo/pipelines/orchestration/metadata.yaml` **before** the `trigger_ranking` block (or insert between `trigger_category_analytics` and `trigger_ranking`):

```yaml
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks:
  - trigger_ranking
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: trigger_edge_scoring
  retry_config: null
  status: not_executed
  timeout: null
  type: data_exporter
  upstream_blocks:
  - trigger_category_analytics
  uuid: trigger_edge_scoring
```

Also update the `downstream_blocks` of the `trigger_category_analytics` block to include `trigger_edge_scoring` (instead of or in addition to `trigger_ranking`), and update `trigger_ranking`'s upstream to be `trigger_edge_scoring`.

---

## Pipeline SLA

| Metric | Target |
|--------|--------|
| Execution time | < 5 min (depends on number of resolved trades) |
| Data freshness | Daily snapshot (triggered once per orchestration cycle) |
| Edge accuracy | ≥ 99% match with manually verified trades |
| Min-max normalisation | Dynamic across all wallets in current batch |

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `magic/default_repo/pipelines/enrichment_edge_scoring/__init__.py` (empty) |
| CREATE | `magic/default_repo/pipelines/enrichment_edge_scoring/metadata.yaml` |
| CREATE | `magic/default_repo/pipelines/enrichment_edge_scoring/triggers/` (empty dir) |
| CREATE | `magic/default_repo/data_loaders/load_resolved_trades.py` |
| CREATE | `magic/default_repo/data_loaders/load_trade_outcomes.py` |
| CREATE | `magic/default_repo/transformers/compute_trade_edge.py` |
| CREATE | `magic/default_repo/data_exporters/export_edge_snapshots.py` |
| CREATE | `magic/default_repo/data_exporters/trigger_edge_scoring.py` |
| EDIT | `magic/default_repo/pipelines/orchestration/metadata.yaml` — insert trigger block between category_analytics and ranking |
