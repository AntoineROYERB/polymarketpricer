# Phase 5 — Follow & Paper Trading — ETL Pipeline

> **Goal**: Create `enrichment_follow_scoring` pipeline to compute `follow_score` and extend `smart_money_detection` to trigger paper trade execution.
> **AI Agent Instructions**: Create the Mage AI pipeline `enrichment_follow_scoring` with data loader, transformer, and exporter. Extend `smart_money_detection` exporters to call the paper trading engine.

---

## Pipeline 1: `enrichment_follow_scoring` (NEW)

### Position in Pipeline Order

```
enrichment_edge_scoring (upstream)
         │
         ▼
enrichment_follow_scoring  ◄── NEW
         │
         ▼
enrichment_ranking_computation (downstream — unchanged)
```

### Data Flow (Global Scoring)

```
         wallet_analytics (edge_score, consistency_score)
         wallet_edge_snapshots (edge_score)
         category_analytics (is_specialist, category_rank)
         trades (for recency + frequency)
                │
                ▼
    load_follow_metrics.py  ───────────────────┐
    (main query: per-wallet metrics)            │
                │                               │
                ▼                               │
    compute_follow_score.py                     │
    (global follow_score formula)               │
                │                               │
                ▼                               │
    export_follow_scores.py                     │
    (UPDATE wallet_analytics                    │
     SET follow_score = ...)                    │
                                                │
    load_follow_metrics.py  ◄───────────────────┘
    (extended query: per-wallet x per-category metrics)
                │
                ▼
    compute_category_follow_scores.py
    (per-category follow_score formula:
     0.25*edge + 0.25*roi_percentile + 0.20*win_rate
      + 0.15*specialist_bonus + 0.10*volume_percentile + 0.05*recency)
                │
                ▼
    export_category_follow_scores.py
    (UPSERT wallet_category_follow_scores
     + UPDATE wallet_analytics.category_follow_scores)
```

### File Manifest

```
magic/default_repo/pipelines/enrichment_follow_scoring/
├── __init__.py
├── metadata.yaml                     # Updated with per-category block
└── triggers/

magic/default_repo/data_loaders/load_follow_metrics.py    # Extended with per-category query
magic/default_repo/transformers/compute_follow_score.py   # Updated global scoring
magic/default_repo/transformers/compute_category_follow_scores.py  # NEW — per-category
magic/default_repo/data_exporters/export_follow_scores.py
magic/default_repo/data_exporters/export_category_follow_scores.py  # NEW
magic/default_repo/data_exporters/trigger_follow_scoring.py
```

---

## 1. Data Loader: `load_follow_metrics.py`

Loads all metrics needed for follow scoring per wallet. Updated to also load per-category data.

### Global metrics query (same as original)

The main query loads per-wallet metrics as shown below.

### Extended query: per-category metrics

A second query loads per-wallet, per-category metrics for the category-level follow scoring:

```sql
SELECT
    ca.wallet,
    ca.category,
    ca.roi,
    ca.win_rate,
    ca.num_trades,
    ca.total_volume,
    ca.is_specialist,
    -- Percentile ranking within category
    PERCENT_RANK() OVER (
        PARTITION BY ca.category
        ORDER BY ca.roi DESC
    ) as roi_percentile,
    PERCENT_RANK() OVER (
        PARTITION BY ca.category
        ORDER BY ca.total_volume DESC
    ) as volume_percentile,
    -- Recency in category
    EXTRACT(DAY FROM (CURRENT_DATE - MAX(t.timestamp::date))) as recency_days,
    -- Global edge for context
    wes.edge_score as global_edge_score,
    -- Global follow_score for context
    wa.follow_score as global_follow_score
FROM category_analytics ca
LEFT JOIN trades t ON t.wallet = ca.wallet
LEFT JOIN markets m ON m.id = t.market_id
    AND (m.mapped_category = ca.category OR m.category = ca.category)
LEFT JOIN (
    SELECT DISTINCT ON (wallet) wallet, edge_score
    FROM wallet_edge_snapshots
    ORDER BY wallet, snapshot_date DESC
) wes ON wes.wallet = ca.wallet
LEFT JOIN wallet_analytics wa ON wa.wallet = ca.wallet
    AND wa.snapshot_date = CURRENT_DATE
WHERE ca.snapshot_date = CURRENT_DATE
GROUP BY ca.wallet, ca.category, ca.roi, ca.win_rate, ca.num_trades,
         ca.total_volume, ca.is_specialist, wes.edge_score, wa.follow_score
```

```python
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@data_loader
def load_follow_metrics(*args, **kwargs) -> DataFrame:
    """Load all metrics needed for follow scoring."""
    engine = create_engine(kwargs.get('db_url'))

    query = """
    WITH wallet_metrics AS (
        SELECT
            wa.wallet,
            -- Edge score (from wallet_edge_snapshots, latest)
            COALESCE(wes.edge_score, 0) AS edge_score,
            -- Consistency score
            COALESCE(wa.consistency_score, 0) AS consistency_score,
            -- Category specialization
            COALESCE(ca.specialist_count, 0) AS specialist_count,
            COALESCE(ca.avg_category_rank, 50) AS avg_category_rank,
            -- Recency
            COALESCE(t.days_since_last_trade, 999) AS days_since_last_trade,
            -- Trade frequency
            COALESCE(t.total_trades, 0) AS total_trades,
            COALESCE(t.months_active, 1) AS months_active
        FROM wallet_analytics wa
        LEFT JOIN (
            SELECT DISTINCT ON (wallet)
                wallet, edge_score
            FROM wallet_edge_snapshots
            ORDER BY wallet, snapshot_date DESC
        ) wes ON wes.wallet = wa.wallet
        LEFT JOIN (
            SELECT
                wallet,
                COUNT(*) FILTER (WHERE is_specialist) AS specialist_count,
                AVG(category_rank) AS avg_category_rank
            FROM category_analytics
            WHERE snapshot_date = CURRENT_DATE
            GROUP BY wallet
        ) ca ON ca.wallet = wa.wallet
        LEFT JOIN (
            SELECT
                wallet,
                EXTRACT(DAY FROM (CURRENT_DATE - MAX(timestamp::date)))::int
                    AS days_since_last_trade,
                COUNT(*) AS total_trades,
                GREATEST(
                    EXTRACT(DAY FROM (CURRENT_DATE - MIN(timestamp::date))) / 30.0,
                    1
                ) AS months_active
            FROM trades
            GROUP BY wallet
        ) t ON t.wallet = wa.wallet
        WHERE wa.snapshot_date = CURRENT_DATE
    )
    SELECT * FROM wallet_metrics
    """
    with engine.connect() as conn:
        df = conn.execute(text(query))
        df = DataFrame(df.fetchall(), columns=df.keys())

    return df


@test
def test_output(df: DataFrame) -> None:
    assert df is not None
    assert not df.empty, "No wallet metrics loaded"
    assert 'wallet' in df.columns
    assert 'edge_score' in df.columns
    assert 'consistency_score' in df.columns
```

## 2. Transformer: `compute_follow_score.py`

```python
import math
from pandas import DataFrame

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


def compute_category_specialization(row: dict) -> float:
    """Score based on specialist count and avg rank."""
    specialist_count = float(row.get('specialist_count', 0))
    avg_rank = float(row.get('avg_category_rank', 50))
    score = 0.5 * min(specialist_count / 8, 1) + 0.5 * max(1 - avg_rank / 100, 0)
    return score


def compute_recency_score(days_since: float) -> float:
    """Exponential decay. Score = e^(-days/90)."""
    return math.exp(-days_since / 90)


def compute_frequency_score(total_trades: float, months_active: float) -> float:
    """Sigmoid normalisation. Score = 1/(1+e^(-0.1*(tpm-10)))."""
    tpm = total_trades / max(months_active, 1)
    return 1 / (1 + math.exp(-0.1 * (tpm - 10)))


@transformer
def compute_follow_score(df: DataFrame, *args, **kwargs) -> DataFrame:
    """Compute follow_score for each wallet."""
    results = []
    for _, row in df.iterrows():
        edge = float(row.get('edge_score', 0))
        consistency = float(row.get('consistency_score', 0))
        spec_score = compute_category_specialization(row)
        recency = compute_recency_score(float(row.get('days_since_last_trade', 999)))
        frequency = compute_frequency_score(
            float(row.get('total_trades', 0)),
            float(row.get('months_active', 1)),
        )

        follow_score = (
            0.30 * edge +
            0.20 * consistency +
            0.20 * spec_score +
            0.15 * recency +
            0.15 * frequency
        )

        results.append({
            'wallet': row['wallet'],
            'follow_score': round(follow_score, 6),
        })

    return DataFrame(results)


@test
def test_output(df: DataFrame) -> None:
    assert df is not None
    assert not df.empty
    assert 'wallet' in df.columns
    assert 'follow_score' in df.columns
    assert df['follow_score'].between(0, 1).all(), "Scores must be in [0, 1]"
```


### Per-Category Transformer

A separate transformer that processes the per-category metrics loaded by the extended query:

```python
import math
from pandas import DataFrame

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


def compute_category_specialist_bonus(is_specialist: bool) -> float:
    """Specialist bonus: 1.0 if specialist, 0.5 otherwise."""
    return 1.0 if is_specialist else 0.5


@transformer
def compute_category_follow_scores(df: DataFrame, *args, **kwargs) -> DataFrame:
    """Compute per-category follow_score for each wallet x category."""
    results = []
    for _, row in df.iterrows():
        edge = float(row.get('global_edge_score', 0))
        roi_percentile = float(row.get('roi_percentile', 0.5))
        win_rate = float(row.get('win_rate', 0))
        is_specialist = bool(row.get('is_specialist', False))
        specialist_bonus = compute_category_specialist_bonus(is_specialist)
        volume_percentile = float(row.get('volume_percentile', 0.5))
        recency_days = float(row.get('recency_days', 999))
        recency_score = math.exp(-recency_days / 90)
        global_follow_score = float(row.get('global_follow_score', 0))

        follow_score = (
            0.25 * edge +
            0.25 * roi_percentile +
            0.20 * win_rate +
            0.15 * specialist_bonus +
            0.10 * volume_percentile +
            0.05 * recency_score
        )
        follow_score = min(max(follow_score, 0), 1)  # clamp to [0, 1]

        # Generate reasons
        reasons = []
        if roi_percentile > 0.90:
            reasons.append(f"Top 10% ROI in {row['category']}")
        if is_specialist:
            reasons.append(f"{row['category']} specialist ({int(row.get('num_trades', 0))} trades)")
        if win_rate > 0.65:
            reasons.append(f"Win rate {win_rate:.0%} in {row['category']}")
        if edge > 0.50:
            reasons.append(f"Positive global edge ({edge:.2f})")
        num_trades = int(row.get('num_trades', 0))
        if num_trades < 15:
            reasons.append(f"Only {num_trades} trades — limited history")
        if recency_days > 90:
            reasons.append(f"No trades in {row['category']} for {int(recency_days/30)} months")
        if win_rate < 0.40:
            reasons.append(f"Win rate below 40% in {row['category']}")
        if not reasons:
            reasons.append("Insufficient data")

        # Recommendation
        recommendation = "FOLLOW" if follow_score >= 0.70 else \
                         "WATCH" if follow_score >= 0.35 else \
                         "IGNORE"

        results.append({
            'wallet': row['wallet'],
            'category': row['category'],
            'follow_score': round(follow_score, 6),
            'recommendation': recommendation,
            'roi_percentile': round(roi_percentile, 6),
            'win_rate': round(win_rate, 6),
            'is_specialist': is_specialist,
            'volume_percentile': round(volume_percentile, 6) if volume_percentile else None,
            'recency_days': int(recency_days) if recency_days != 999 else None,
            'reasons': reasons,
            'global_follow_score': round(global_follow_score, 6),
        })

    return DataFrame(results)


@test
def test_output(df: DataFrame) -> None:
    assert df is not None
    assert 'wallet' in df.columns
    assert 'category' in df.columns
    assert 'follow_score' in df.columns
    assert 'recommendation' in df.columns
    if not df.empty:
        assert df['follow_score'].between(0, 1).all(), "Scores must be in [0, 1]"
        valid_recs = {'FOLLOW', 'WATCH', 'IGNORE'}
        assert df['recommendation'].isin(valid_recs).all(), "Invalid recommendation value"
```

## 3. Data Exporter: `export_follow_scores.py`

```python
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def export_follow_scores(df: DataFrame, *args, **kwargs) -> None:
    """Update wallet_analytics with follow_score."""
    engine = create_engine(kwargs.get('db_url'))

    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("""
                    UPDATE wallet_analytics
                    SET follow_score = :score
                    WHERE wallet = :wallet
                      AND snapshot_date = CURRENT_DATE
                """),
                {"wallet": row["wallet"], "score": row["follow_score"]},
            )


@test
def test_output(*args) -> None:
    pass
```

---

## 3b. Data Exporter: `export_category_follow_scores.py`

After computing per-category scores in the pipeline, export them to `wallet_category_follow_scores` and update `wallet_analytics.category_follow_scores`.

```python
from datetime import date
import json
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@data_exporter
def export_category_follow_scores(df: DataFrame, *args, **kwargs) -> None:
    """Export per-category follow scores to wallet_category_follow_scores.

    Input DataFrame columns:
        wallet, category, follow_score, recommendation, roi_percentile,
        win_rate, is_specialist, volume_percentile, recency_days, reasons, global_follow_score
    """
    if df.empty:
        return

    engine = create_engine(kwargs.get('db_url'))
    today = date.today()
    category_scores_by_wallet = {}

    with engine.begin() as conn:
        for _, row in df.iterrows():
            # Upsert into wallet_category_follow_scores
            conn.execute(
                text("""
                    INSERT INTO wallet_category_follow_scores
                        (wallet, category, snapshot_date, follow_score, recommendation,
                         roi_percentile, win_rate, is_specialist, volume_percentile,
                         recency_days, reasons, global_follow_score)
                    VALUES
                        (:wallet, :category, :snapshot_date, :follow_score, :recommendation,
                         :roi_percentile, :win_rate, :is_specialist, :volume_percentile,
                         :recency_days, :reasons::jsonb, :global_follow_score)
                    ON CONFLICT (wallet, category, snapshot_date)
                    DO UPDATE SET
                        follow_score = EXCLUDED.follow_score,
                        recommendation = EXCLUDED.recommendation,
                        roi_percentile = EXCLUDED.roi_percentile,
                        win_rate = EXCLUDED.win_rate,
                        is_specialist = EXCLUDED.is_specialist,
                        volume_percentile = EXCLUDED.volume_percentile,
                        recency_days = EXCLUDED.recency_days,
                        reasons = EXCLUDED.reasons,
                        global_follow_score = EXCLUDED.global_follow_score
                """),
                {
                    "wallet": row["wallet"],
                    "category": row["category"],
                    "snapshot_date": today,
                    "follow_score": row["follow_score"],
                    "recommendation": row["recommendation"],
                    "roi_percentile": row.get("roi_percentile"),
                    "win_rate": row.get("win_rate"),
                    "is_specialist": row.get("is_specialist", False),
                    "volume_percentile": row.get("volume_percentile"),
                    "recency_days": row.get("recency_days"),
                    "reasons": json.dumps(row.get("reasons", [])),
                    "global_follow_score": row.get("global_follow_score"),
                },
            )

            # Accumulate JSONB for wallet_analytics update
            wallet_key = row["wallet"]
            if wallet_key not in category_scores_by_wallet:
                category_scores_by_wallet[wallet_key] = {}
            category_scores_by_wallet[wallet_key][row["category"]] = {
                "follow_score": float(row["follow_score"]),
                "recommendation": row["recommendation"],
            }

        # Update wallet_analytics.category_follow_scores JSONB
        for wallet, scores in category_scores_by_wallet.items():
            conn.execute(
                text("""
                    UPDATE wallet_analytics
                    SET category_follow_scores = :scores::jsonb
                    WHERE wallet = :wallet
                      AND snapshot_date = :snapshot_date
                """),
                {
                    "wallet": wallet,
                    "snapshot_date": today,
                    "scores": json.dumps(scores),
                },
            )


@test
def test_output(*args) -> None:
    pass
```

## 4. Trigger: `trigger_follow_scoring.py`

```python
if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


@data_exporter
def trigger_follow_scoring(*args, **kwargs) -> None:
    """Trigger the next pipeline in the orchestration sequence."""
    return {}
```

---

## Pipeline 2: Extension to `smart_money_detection`

### Modified `export_alerts.py`

After inserting alerts into the `alerts` table, extend the exporter to generate paper trades for followed wallets with auto-copy enabled.

Add to the existing `export_alerts.py` (or create a parallel exporter):

```python
@data_exporter
def export_alerts_and_generate_paper_trades(df: DataFrame, *args, **kwargs) -> None:
    """Export alerts to DB, then generate paper trades for followed wallets."""
    from sqlalchemy import create_engine, text

    engine = create_engine(kwargs.get('db_url'))

    # Step 1: Export alerts (existing logic)
    # ... (existing alert export code) ...

    # Step 2: Generate paper trades for followed wallets
    with engine.connect() as conn:
        # Find active follows with auto_copy_enabled that just triggered alerts
        follow_query = text("""
            SELECT
                wf.wallet,
                wf.copy_mode,
                wf.copy_value,
                wf.category_filter,
                wf.user_id
            FROM wallet_follows wf
            WHERE wf.active = true
              AND wf.auto_copy_enabled = true
        """)
        follows = conn.execute(follow_query).fetchall()

        if not follows:
            return  # No auto-copy follows

        # Get the alerts that were just inserted
        alerts_query = text("""
            SELECT a.*
            FROM alerts a
            WHERE a.detected_at >= NOW() - INTERVAL '5 minutes'
              AND a.notified_at IS NULL
        """)
        new_alerts = conn.execute(alerts_query).fetchall()

        # Match alerts to follows and execute paper trades
        for alert in new_alerts:
            for follow in follows:
                if follow.wallet != alert.wallet:
                    continue

                # Check category filter
                if follow.category_filter:
                    import json
                    cats = json.loads(follow.category_filter)
                    if alert.category not in cats:
                        continue

                # Execute paper trade
                # This calls the paper trading engine via a stored procedure
                # or directly via SQL operations
                conn.execute(
                    text("""
                        SELECT execute_paper_trade(
                            :user_id, :wallet, :copy_mode, :copy_value,
                            :market_id, :outcome, :action, :position_size,
                            :alert_id
                        )
                    """),
                    {
                        "user_id": follow.user_id,
                        "wallet": follow.wallet,
                        "copy_mode": follow.copy_mode,
                        "copy_value": float(follow.copy_value),
                        "market_id": alert.market_id,
                        "outcome": "",  # resolve from alert
                        "action": alert.action,
                        "position_size": float(alert.position_size),
                        "alert_id": alert.id,
                    },
                )
```

> **Note**: In practice, the paper trade generation is better implemented as a separate lightweight service triggered by new alert insertion (via a DB trigger or a background worker), rather than inside the ETL pipeline itself. See architecture note below.

---

## Alternative Architecture: Separate Paper Trade Generator Service

Instead of extending `smart_money_detection`, create a lightweight background service that polls the `alerts` table for new unnotified alerts and executes paper trades:

```
alert inserted into alerts table
        │
        ▼
  paper_trade_generator.py (background task, polls every 10s)
        │
        ▼
  Check if alert.wallet is followed with auto_copy_enabled
        │
        ▼
  Execute paper trade via paper_trading.py service
        │
        ▼
  Write to paper_trades + paper_positions + update portfolio
```

This approach:
- Keeps the ETL pipeline clean (no cross-concern coupling)
- Works with the existing `alert_delivery_loop` pattern
- Can be added as a new background task in `app/main.py`

**Implementation:**

```python
# app/services/paper_trade_generator.py

async def paper_trade_generation_loop(db: AsyncSession):
    """Background task: poll for new alerts and generate paper trades."""
    while True:
        try:
            # Find new alerts not yet processed for paper trading
            result = await db.execute(
                text("""
                    SELECT a.*, wf.id as follow_id, wf.copy_mode, wf.copy_value,
                           wf.category_filter, wf.user_id
                    FROM alerts a
                    JOIN wallet_follows wf ON wf.wallet = a.wallet
                        AND wf.active = true
                        AND wf.auto_copy_enabled = true
                    LEFT JOIN paper_trades pt ON pt.source_alert_id = a.id
                    WHERE pt.id IS NULL  -- not yet processed
                      AND a.detected_at >= NOW() - INTERVAL '1 hour'
                    ORDER BY a.detected_at
                    LIMIT 20
                """)
            )
            alerts = result.all()

            for alert in alerts:
                # Check category filter
                if alert.category_filter:
                    import json
                    cats = json.loads(alert.category_filter)
                    if alert.category not in cats:
                        continue

                # Execute paper trade
                from app.services.paper_trading import execute_copy_trade
                follow = await db.execute(
                    select(WalletFollow).where(WalletFollow.id == alert.follow_id)
                )
                follow_obj = follow.scalar_one()
                await execute_copy_trade(db, dict(alert._mapping), follow_obj)

        except Exception as e:
            logger.error(f"Paper trade generation error: {e}")

        await asyncio.sleep(10)
```

---

## Orchestration Update

Update `orchestration` pipeline to include `enrichment_follow_scoring`:

```
ingestion_market_discovery
  → ingestion_wallet_discovery
    → ingestion_position_sync
      → ingestion_pnl
        → ingestion_trade_history
          → enrichment_analytics_computation
            → enrichment_ranking_computation
              → category_analytics
                → enrichment_edge_scoring
                  → enrichment_follow_scoring  ◄── NEW
                    → smart_money_detection
                      → verify_etl_output
```

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `magic/default_repo/pipelines/enrichment_follow_scoring/` (dir + metadata.yaml) |
| CREATE | `magic/default_repo/data_loaders/load_follow_metrics.py` |
| CREATE | `magic/default_repo/transformers/compute_follow_score.py` |
| CREATE | `magic/default_repo/transformers/compute_category_follow_scores.py` |
| CREATE | `magic/default_repo/data_exporters/export_follow_scores.py` |
| CREATE | `magic/default_repo/data_exporters/export_category_follow_scores.py` |
| CREATE | `magic/default_repo/data_exporters/trigger_follow_scoring.py` |
| MODIFY | `magic/default_repo/pipelines/smart_money_detection/data_exporters/export_alerts.py` — add paper trade logic |
| MODIFY | `magic/default_repo/pipelines/orchestration/metadata.yaml` — add enrichment_follow_scoring |
| CREATE | `app/services/paper_trade_generator.py` — background task |

---

## Verification

```bash
# Run follow scoring pipeline
docker compose exec mage mage run /home/src/default_repo enrichment_follow_scoring

# Verify follow_score populated
psql -U app -d polymarket -c "
    SELECT wallet, follow_score
    FROM wallet_analytics
    WHERE follow_score IS NOT NULL
    ORDER BY follow_score DESC
    LIMIT 10;
"
```
