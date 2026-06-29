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

### Data Flow

```
         wallet_analytics (edge_score, consistency_score)
         wallet_edge_snapshots (edge_score)
         category_analytics (is_specialist, category_rank)
         trades (for recency + frequency)
                │
                ▼
    load_follow_metrics.py
    (PG query: join all relevant metrics per wallet)
                │
                ▼
    compute_follow_score.py
    (transformer — implements follow scoring formula:
     0.30*edge + 0.20*consistency + 0.20*specialization
     + 0.15*recency + 0.15*frequency)
                │
                ▼
    export_follow_scores.py
    (UPDATE wallet_analytics SET follow_score = ...)
```

### File Manifest

```
magic/default_repo/pipelines/enrichment_follow_scoring/
├── __init__.py
├── metadata.yaml
└── triggers/

magic/default_repo/data_loaders/load_follow_metrics.py
magic/default_repo/transformers/compute_follow_score.py
magic/default_repo/data_exporters/export_follow_scores.py
magic/default_repo/data_exporters/trigger_follow_scoring.py
```

---

## 1. Data Loader: `load_follow_metrics.py`

Loads all metrics needed for follow scoring per wallet.

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
| CREATE | `magic/default_repo/data_exporters/export_follow_scores.py` |
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
