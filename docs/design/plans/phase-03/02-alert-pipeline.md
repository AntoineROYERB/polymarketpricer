# Phase 3 — Smart Money Detection — Alert Pipeline

> **Goal**: Detect position changes (new entries, increases, decreases, exits) from top-scoring wallets, filter by alert rules, and write to the `alerts` table.
> **AI Agent Instructions**: Create a new Mage AI pipeline `smart_money_detection` with its data loader, transformer, data exporter, and register it in the orchestration pipeline.

---

## Pipeline: `smart_money_detection`

### Data Flow

```
ingestion_position_sync (upstream)
         │
         ▼
  position_history  ──►  load_recent_changes
                           (PG query: last N min)
         │
         ▼
  detect_alerts  ──►  classify action type
  (transformer)        enrich with wallet_score,
                       category, market_question,
                       liquidity
                       apply alert_rules thresholds
                       dedup by cooldown window
         │
         ▼
  export_alerts  ──►  INSERT into `alerts`
                       (notified_at = NULL)
```

### File Manifest

```
magic/default_repo/pipelines/smart_money_detection/
├── __init__.py              (empty)
├── metadata.yaml            (pipeline definition)
└── triggers/                (empty directory)

magic/default_repo/data_loaders/load_recent_position_changes.py
magic/default_repo/transformers/detect_smart_money_alerts.py
magic/default_repo/data_exporters/export_alerts.py
magic/default_repo/data_exporters/trigger_smart_money.py
```

---

## 1. Data Loader: `load_recent_position_changes.py`

Queries `position_history` for changes within the detection window, joins with markets for enrichment.

```python
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"
DETECTION_WINDOW_MINUTES = 10  # How far back to look for changes


@data_loader
def load_data(*args, **kwargs) -> dict[str, DataFrame]:
    """Load recent position changes, wallet scores, and alert rules from PG."""
    engine = create_engine(DATABASE_URL)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=DETECTION_WINDOW_MINUTES)

    with engine.connect() as conn:
        # Step 1: recent position changes with market enrichment
        changes = conn.execute(text("""
            SELECT
                ph.wallet,
                ph.market_id,
                ph.shares_before,
                ph.shares_after,
                ph.pnl_change,
                ph.recorded_at,
                m.question AS market_question,
                m.liquidity_usd,
                COALESCE(m.mapped_category, m.category, 'unknown') AS category
            FROM position_history ph
            JOIN markets m ON m.id = ph.market_id
            WHERE ph.recorded_at >= :cutoff
            ORDER BY ph.recorded_at DESC
        """), {"cutoff": cutoff}).mappings().all()

        # Step 2: latest wallet scores
        scores = conn.execute(text("""
            SELECT DISTINCT ON (wallet) wallet, wallet_score
            FROM wallet_analytics
            ORDER BY wallet, snapshot_date DESC
        """)).mappings().all()

        # Step 3: active alert rules (global default first)
        rules = conn.execute(text("""
            SELECT * FROM alert_rules WHERE active = true
            ORDER BY wallet NULLS LAST
        """)).mappings().all()

    engine.dispose()

    return {
        "changes": DataFrame(changes) if changes else DataFrame(columns=[
            "wallet", "market_id", "shares_before", "shares_after",
            "pnl_change", "recorded_at", "market_question",
            "liquidity_usd", "category",
        ]),
        "scores": DataFrame(scores) if scores else DataFrame(
            columns=["wallet", "wallet_score"]
        ),
        "rules": DataFrame(rules) if rules else DataFrame(columns=[
            "id", "wallet", "min_score", "min_position_size",
            "min_liquidity", "cooldown_minutes", "discord_webhook_url", "active",
        ]),
    }


@test
def test_output(result) -> None:
    assert "changes" in result, "Missing changes DataFrame"
    assert "scores" in result, "Missing scores DataFrame"
    assert "rules" in result, "Missing rules DataFrame"
```

---

## 2. Transformer: `detect_smart_money_alerts.py`

Core detection logic. Given position changes, wallet scores, and rules, produce alert rows.

```python
from datetime import datetime, timezone
from pandas import DataFrame, merge, to_numeric

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

ALERT_COLS = [
    "wallet", "market_id", "action", "price", "position_size",
    "wallet_score", "category", "market_question", "detected_at",
]


def classify_action(shares_before, shares_after):
    """Classify a position change into one of 4 action types.

    Returns None if there is no meaningful change (both 0 or equal).
    """
    before = float(shares_before or 0)
    after = float(shares_after or 0)

    if before == 0 and after > 0:
        return "NEW_POSITION"
    elif after > before:
        return "POSITION_INCREASE"
    elif after < before and after > 0:
        return "POSITION_DECREASE"
    elif after == 0 and before > 0:
        return "FULL_EXIT"
    return None


def get_applicable_rule(wallet: str, rules_df: DataFrame) -> dict:
    """Find the matching rule for a wallet, falling back to global default."""
    wallet_rule = rules_df[rules_df["wallet"] == wallet]
    if not wallet_rule.empty:
        return wallet_rule.iloc[0].to_dict()
    global_rule = rules_df[rules_df["wallet"].isna()]
    if not global_rule.empty:
        return global_rule.iloc[0].to_dict()
    # Hardcoded safety fallback
    return {
        "min_score": 80.0,
        "min_position_size": 500.0,
        "min_liquidity": 1000.0,
        "cooldown_minutes": 15,
    }


@transformer
def detect_alerts(data: dict, *args, **kwargs) -> DataFrame:
    """Apply detection logic: classify, enrich, filter, return alert rows."""
    changes = data.get("changes", DataFrame())
    scores = data.get("scores", DataFrame())
    rules = data.get("rules", DataFrame())

    if changes.empty:
        print("No position changes to process")
        return DataFrame(columns=ALERT_COLS)

    now = datetime.now(timezone.utc)

    # Merge wallet scores into changes
    changes = changes.merge(scores, on="wallet", how="left", suffixes=("", "_score"))
    changes["wallet_score"] = to_numeric(
        changes.get("wallet_score"), errors="coerce"
    ).fillna(0)

    # Ensure numeric types
    changes["shares_before"] = to_numeric(changes["shares_before"], errors="coerce").fillna(0)
    changes["shares_after"] = to_numeric(changes["shares_after"], errors="coerce").fillna(0)
    if "liquidity_usd" in changes.columns:
        changes["liquidity_usd"] = to_numeric(
            changes["liquidity_usd"], errors="coerce"
        ).fillna(0)

    alert_rows = []

    for _, row in changes.iterrows():
        # 1. Classify action
        action = classify_action(row["shares_before"], row["shares_after"])
        if action is None:
            continue

        # 2. Look up applicable rule
        rule = get_applicable_rule(row["wallet"], rules)

        # 3. Threshold: wallet_score >= min_score
        if float(row.get("wallet_score", 0)) < float(rule.get("min_score", 80)):
            continue

        # 4. Compute position size (USD magnitude of change)
        position_size = abs(
            float(row["shares_after"]) - float(row["shares_before"])
        )
        if position_size < float(rule.get("min_position_size", 500)):
            continue

        # 5. Threshold: market liquidity >= min_liquidity
        liquidity = float(row.get("liquidity_usd", 0) or 0)
        if liquidity < float(rule.get("min_liquidity", 1000)):
            continue

        # 6. Estimate price (pnl_change / position_size)
        pnl = float(row.get("pnl_change", 0) or 0)
        price = abs(pnl) / position_size if position_size > 0 else 0.0

        alert_rows.append({
            "wallet": row["wallet"],
            "market_id": row["market_id"],
            "action": action,
            "price": price,
            "position_size": position_size,
            "wallet_score": float(row.get("wallet_score", 0)),
            "category": row.get("category", "unknown"),
            "market_question": row.get("market_question", ""),
            "detected_at": now,
        })

    print(f"Detected {len(alert_rows)} alerts from {len(changes)} position changes")
    return DataFrame(alert_rows) if alert_rows else DataFrame(columns=ALERT_COLS)


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert "action" in df.columns, "Missing action column"
        valid_actions = {
            "NEW_POSITION", "POSITION_INCREASE",
            "POSITION_DECREASE", "FULL_EXIT",
        }
        assert df["action"].isin(valid_actions).all(), "Invalid action value"
```

---

## 3. Data Exporter: `export_alerts.py`

Inserts alerts into the `alerts` table with cooldown dedup check.

```python
from datetime import datetime, timezone
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_exporter
def export_data(alerts: DataFrame, **kwargs) -> None:
    """Insert alerts into PG, skipping duplicates within cooldown window."""
    if alerts.empty:
        print("No alerts to export")
        return

    engine = create_engine(DATABASE_URL)
    inserted = 0
    skipped = 0

    with engine.begin() as conn:
        for _, row in alerts.iterrows():
            # Cooldown check: skip if same wallet+market+action within window
            existing = conn.execute(text("""
                SELECT 1 FROM alerts
                WHERE wallet = :wallet
                  AND market_id = :market_id
                  AND action = :action
                  AND detected_at > NOW() - (
                      SELECT COALESCE(
                          (
                              SELECT (cooldown_minutes || ' minutes')::interval
                              FROM alert_rules
                              WHERE (wallet = :wallet2 OR wallet IS NULL)
                              ORDER BY wallet NULLS LAST
                              LIMIT 1
                          ),
                          '15 minutes'::interval
                      )
                  )
                LIMIT 1
            """), {
                "wallet": row["wallet"],
                "market_id": row["market_id"],
                "action": row["action"],
                "wallet2": row["wallet"],
            }).scalar()

            if existing:
                skipped += 1
                continue

            conn.execute(text("""
                INSERT INTO alerts
                    (wallet, market_id, action, price, position_size,
                     wallet_score, category, market_question, detected_at)
                VALUES
                    (:wallet, :market_id, :action, :price, :position_size,
                     :wallet_score, :category, :market_question, :detected_at)
            """), {
                "wallet": row["wallet"],
                "market_id": row["market_id"],
                "action": row["action"],
                "price": float(row.get("price", 0)),
                "position_size": float(row.get("position_size", 0)),
                "wallet_score": float(row.get("wallet_score", 0)),
                "category": str(row.get("category", "unknown")),
                "market_question": str(row.get("market_question", "")),
                "detected_at": row.get("detected_at", datetime.now(timezone.utc)),
            })
            inserted += 1

    engine.dispose()
    print(f"Alerts exported: {inserted} inserted, {skipped} skipped (cooldown)")


@test
def test_output(*args) -> None:
    pass
```

---

## 4. Pipeline Metadata

Create `magic/default_repo/pipelines/smart_money_detection/metadata.yaml`:

```yaml
blocks:
- all_upstream_blocks_executed: true
  color: null
  configuration: {}
  downstream_blocks:
  - load_recent_position_changes
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: load_recent_position_changes
  retry_config: null
  status: not_executed
  timeout: null
  type: data_loader
  upstream_blocks: []
  uuid: load_recent_position_changes
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks:
  - detect_smart_money_alerts
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: detect_smart_money_alerts
  retry_config: null
  status: not_executed
  timeout: null
  type: transformer
  upstream_blocks:
  - load_recent_position_changes
  uuid: detect_smart_money_alerts
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks: []
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: export_alerts
  retry_config: null
  status: not_executed
  timeout: null
  type: data_exporter
  upstream_blocks:
  - detect_smart_money_alerts
  uuid: export_alerts
cache_block_output_in_memory: false
callbacks: []
concurrency_config: {}
conditionals: []
created_at: null
data_integration: null
description: "Detect smart money position changes and generate alerts"
executor_config: {}
executor_count: 1
executor_type: null
extensions: {}
name: smart_money_detection
notification_config: {}
remote_variables_dir: null
retry_config: {}
run_pipeline_in_one_process: false
settings:
  triggers: null
spark_config: {}
tags: []
type: python
uuid: smart_money_detection
variables_dir: /home/src/mage_data/default_repo
widgets: []
```

---

## 5. Orchestration Registration

### Create trigger block

Create `magic/default_repo/data_exporters/trigger_smart_money.py`:

```python
if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline


@data_exporter
def export_data(**kwargs) -> None:
    trigger_pipeline(
        'smart_money_detection',
        variables={},
        check_status=False,
        error_on_failure=True,
        poll_interval=30,
        poll_timeout=120,
        schedule_name=None,
        verbose=True,
    )
```

### Edit orchestration metadata

Add this block at the end of `magic/default_repo/pipelines/orchestration/metadata.yaml` (after the `trigger_verify` block):

```yaml
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks: []
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: trigger_smart_money
  retry_config: null
  status: not_executed
  timeout: null
  type: data_exporter
  upstream_blocks:
  - trigger_verify
  uuid: trigger_smart_money
```

Also add `trigger_smart_money` to the downstream_blocks of `trigger_verify`:

```yaml
  downstream_blocks:
  - trigger_smart_money
```

---

## Pipeline SLA

| Metric | Target |
|---|---|
| Execution time | < 30s |
| Detection latency (max) | ~5 min (Mage poll interval + execution) |
| False positives (expected) | < 5% |
| Dedup accuracy | 100% (no duplicate alerts within cooldown) |

---

## Files to Create / Modify

| Action | Path |
|---|---|
| CREATE | `magic/default_repo/pipelines/smart_money_detection/__init__.py` (empty) |
| CREATE | `magic/default_repo/pipelines/smart_money_detection/metadata.yaml` |
| CREATE | `magic/default_repo/pipelines/smart_money_detection/triggers/` (empty dir — placeholder) |
| CREATE | `magic/default_repo/data_loaders/load_recent_position_changes.py` |
| CREATE | `magic/default_repo/transformers/detect_smart_money_alerts.py` |
| CREATE | `magic/default_repo/data_exporters/export_alerts.py` |
| CREATE | `magic/default_repo/data_exporters/trigger_smart_money.py` |
| EDIT | `magic/default_repo/pipelines/orchestration/metadata.yaml` — add trigger block + wire downstream |
