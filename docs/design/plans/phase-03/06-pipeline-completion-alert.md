# Phase 3 — Smart Money Detection — Pipeline Completion Alert & Best Candidate

> **Goal**: Notify the Discord webhook when the ETL orchestration finishes, including run summary (duration, rows loaded, errors). If the `smart_money_detection` pipeline produces zero alerts because no candidate met thresholds, still nominate the **best candidate** — the position change that came closest — so the user can make a judgment call.
> **AI Agent Instructions**: Modify the Mage AI orchestration pipeline to add a final notification block. Create a new transformer `nominate_best_candidate.py` that ranks sub-threshold position changes.

---

## Architecture

A new block is added at the **very end** of the orchestration pipeline (after `trigger_smart_money`). This block:

1. Collects run metadata from all upstream blocks via Mage's runtime context
2. Queries the `alerts` table to see if any alerts were produced by `smart_money_detection`
3. If zero alerts: calls a new transformer `nominate_best_candidate` that picks the single best candidate that was filtered out
4. Sends a single Discord webhook embed with:
   - Pipeline run summary (total duration, per-pipeline status, row counts)
   - Number of alerts generated (or "no alerts — best candidate nominated:")

```
┌─────────────────────────────────────────────────────────┐
│              Orchestration Pipeline                      │
│                                                          │
│  trigger_market_discovery ─► trigger_wallet_discovery │
│         │                                        │      │
│         ▼                                        ▼      │
│  ... (all existing pipeline triggers) ...                │
│         │                                                │
│         ▼                                                │
│  trigger_smart_money                                     │
│         │                                                │
│         ▼                                                │
│  notify_completion  ◄── nominate_best_candidate          │
│  (data exporter)         (transformer, optional)         │
│         │                                                │
│         ▼                                                │
│  Discord Webhook (httpx POST)                            │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Environment Configuration

No new env vars needed — reuse `DISCORD_WEBHOOK_URL` (already wired in the `app` service). The notification will be sent from within Mage, so we need to pass the webhook URL into the Mage container.

### Update `docker-compose.yml`

Add to the `mage` service:

```yaml
environment:
  # ... existing vars ...
  DISCORD_WEBHOOK_URL: "${DISCORD_WEBHOOK_URL}"
```

---

## 2. Data Exporter: `notify_pipeline_completion.py`

Creates `magic/default_repo/data_exporters/notify_pipeline_completion.py`.

Responsible for:
- Collecting runtime metadata from all upstream trigger blocks via Mage's `kwargs`
- Querying `SELECT COUNT(*) FROM alerts WHERE detected_at >= NOW() - interval '10 minutes'`
- If count = 0: invoking `nominate_best_candidate` logic (or importing from a transformer)
- Building and sending a Discord embed via httpx POST

```python
from datetime import datetime, timezone
from pandas import DataFrame
from sqlalchemy import create_engine, text
import httpx
import os
import time

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://app:devpassword@postgres:5432/polymarket")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def _build_summary_embed(
    start_time: float,
    pipeline_statuses: dict[str, str],
    alert_count: int,
    best_candidate: dict | None = None,
) -> dict:
    """Build a Discord embed summarising the full ETL run."""
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    status_lines = "\n".join(
        f"• `{name}`: {status}" for name, status in pipeline_statuses.items()
    )

    fields = [
        {
            "name": "⏱ Duration",
            "value": f"{minutes}m {seconds}s",
            "inline": True,
        },
        {
            "name": "📊 Pipelines",
            "value": status_lines or "None",
            "inline": False,
        },
        {
            "name": "🚨 Alerts Generated",
            "value": str(alert_count),
            "inline": True,
        },
    ]

    if alert_count == 0 and best_candidate:
        fields.append({
            "name": "🏆 Best Candidate (sub-threshold)",
            "value": (
                f"Wallet: `{best_candidate['wallet'][:10]}...{best_candidate['wallet'][-4:]}`\n"
                f"Action: {best_candidate['action']}\n"
                f"Score: {best_candidate['wallet_score']} (required ≥ {best_candidate['min_score']})\n"
                f"Position Size: ${best_candidate['position_size']:,.2f}\n"
                f"Market: {best_candidate['market_question']}"
            ),
            "inline": False,
        })

    return {
        "embeds": [{
            "title": "✅ ETL Pipeline Run Complete",
            "color": 0x5865F2,  # Discord blurple
            "fields": fields,
            "footer": {"text": "Polymarket ETL Orchestration"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }


@data_exporter
def export_data(data: dict, *args, **kwargs) -> None:
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set — skipping notification")
        return

    start_time = kwargs.get("pipeline_run_started_at", time.time())

    # Collect pipeline statuses from upstream block metadata
    pipeline_statuses = {}
    for key, val in kwargs.items():
        if key.startswith("trigger_") and isinstance(val, dict):
            status = val.get("status", "unknown")
            pipeline_statuses[key.removeprefix("trigger_")] = status

    # Count alerts generated in the last 10 minutes
    engine = create_engine(DATABASE_URL)
    alert_count = 0
    best_candidate = None

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FROM alerts
            WHERE detected_at >= NOW() - INTERVAL '10 minutes'
        """)).scalar()
        alert_count = result or 0

        if alert_count == 0:
            # Query the best sub-threshold candidate
            row = conn.execute(text("""
                SELECT
                    ph.wallet,
                    ph.market_id,
                    ph.shares_before,
                    ph.shares_after,
                    ph.pnl_change,
                    ph.recorded_at,
                    m.question AS market_question,
                    COALESCE(wa.wallet_score, 0) AS wallet_score,
                    COALESCE(ar.min_score, 80) AS min_score,
                    COALESCE(ar.min_position_size, 500) AS min_position_size
                FROM position_history ph
                JOIN markets m ON m.id = ph.market_id
                LEFT JOIN (
                    SELECT DISTINCT ON (wallet) wallet, wallet_score
                    FROM wallet_analytics
                    ORDER BY wallet, snapshot_date DESC
                ) wa ON wa.wallet = ph.wallet
                LEFT JOIN alert_rules ar ON ar.wallet IS NULL AND ar.active = true
                WHERE ph.recorded_at >= NOW() - INTERVAL '10 minutes'
                  AND ph.shares_before != ph.shares_after
                ORDER BY wa.wallet_score DESC NULLS LAST
                LIMIT 1
            """)).mappings().first()

            if row:
                raw = dict(row)
                before = float(raw.get("shares_before", 0))
                after = float(raw.get("shares_after", 0))
                if before == 0 and after > 0:
                    action = "NEW_POSITION"
                elif after > before:
                    action = "POSITION_INCREASE"
                elif after < before and after > 0:
                    action = "POSITION_DECREASE"
                elif after == 0 and before > 0:
                    action = "FULL_EXIT"
                else:
                    action = "UNKNOWN"

                best_candidate = {
                    "wallet": raw["wallet"],
                    "action": action,
                    "wallet_score": float(raw.get("wallet_score", 0)),
                    "min_score": float(raw.get("min_score", 80)),
                    "position_size": abs(float(after) - float(before)),
                    "market_question": raw.get("market_question", ""),
                }

    engine.dispose()

    embed = _build_summary_embed(start_time, pipeline_statuses, alert_count, best_candidate)

    # Send to Discord
    try:
        resp = httpx.post(DISCORD_WEBHOOK_URL, json=embed, timeout=10.0)
        if resp.status_code in (200, 204):
            print("Orchestration completion notification sent to Discord")
        else:
            print(f"Discord webhook returned {resp.status_code}")
    except httpx.RequestError as e:
        print(f"Failed to send Discord notification: {e}")


@test
def test_output(*args) -> None:
    pass
```

---

## 3. Transformer: `nominate_best_candidate.py`

> **Note**: In the current design, the best-candidate logic lives directly inside `notify_pipeline_completion.py` (inline query) to keep it simple. This separate transformer is **optional** — create it only if the best-candidate logic needs to be reused independently (e.g., exposed via an API). For the MVP, the inline approach is sufficient.

If a standalone transformer is preferred later, create `magic/default_repo/transformers/nominate_best_candidate.py`:

```python
from pandas import DataFrame, to_numeric

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer


def classify_action(shares_before, shares_after):
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


@transformer
def nominate(data: dict, *args, **kwargs) -> dict:
    """Pick the single best candidate among sub-threshold position changes."""
    changes = data.get("changes", DataFrame())
    if changes.empty:
        return {"best_candidate": None}

    # Ensure numeric
    for col in ("wallet_score", "shares_before", "shares_after"):
        if col in changes.columns:
            changes[col] = to_numeric(changes[col], errors="coerce").fillna(0)

    # Sort by wallet_score descending, pick the top
    best = changes.sort_values("wallet_score", ascending=False).iloc[0]
    action = classify_action(
        best.get("shares_before", 0), best.get("shares_after", 0)
    )

    return {
        "best_candidate": {
            "wallet": str(best.get("wallet", "")),
            "action": action or "UNKNOWN",
            "position_size": abs(
                float(best.get("shares_after", 0)) - float(best.get("shares_before", 0))
            ),
            "wallet_score": float(best.get("wallet_score", 0)),
            "market_question": str(best.get("market_question", "")),
        }
    }
```

---

## 4. Orchestration Registration

### Create trigger/notification block

Create `magic/default_repo/data_exporters/trigger_completion_notification.py`:

```python
if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from mage_ai.orchestration.triggers.api import trigger_pipeline


@data_exporter
def export_data(**kwargs) -> None:
    trigger_pipeline(
        'notify_pipeline_completion',
        variables={},
        check_status=False,
        error_on_failure=True,
        poll_interval=30,
        poll_timeout=120,
        schedule_name=None,
        verbose=True,
    )
```

(Alternatively, if we want to keep it as a single block within the orchestration pipeline without a separate sub-pipeline, we can directly add `notify_pipeline_completion` as a data_exporter block in the orchestration metadata and skip the trigger indirection.)

### Recommended: Single-block approach

Since the notification logic is lightweight, add `notify_pipeline_completion` **directly** as the final block in the orchestration pipeline (no sub-pipeline trigger). This is simpler and avoids an extra pipeline context switch.

#### Edit `magic/default_repo/pipelines/orchestration/metadata.yaml`

Add after the `trigger_smart_money` block:

```yaml
- all_upstream_blocks_executed: false
  color: null
  configuration: {}
  downstream_blocks: []
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: notify_pipeline_completion
  retry_config: null
  status: not_executed
  timeout: null
  type: data_exporter
  upstream_blocks:
  - trigger_smart_money
  uuid: notify_pipeline_completion
```

Also append `notify_pipeline_completion` to the `downstream_blocks` of `trigger_smart_money`:

```yaml
  downstream_blocks:
  - notify_pipeline_completion
```

---

## 5. Pipeline Metadata

No separate pipeline needed (single block in orchestration). If we want a standalone pipeline for reuse, create:

```yaml
# magic/default_repo/pipelines/notify_pipeline_completion/metadata.yaml
blocks:
- all_upstream_blocks_executed: true
  color: null
  configuration: {}
  downstream_blocks: []
  executor_config: null
  executor_type: local_python
  has_callback: null
  language: python
  name: notify_pipeline_completion
  retry_config: null
  status: not_executed
  timeout: null
  type: data_exporter
  upstream_blocks: []
  uuid: notify_pipeline_completion
cache_block_output_in_memory: false
callbacks: []
concurrency_config: {}
conditionals: []
created_at: null
data_integration: null
description: "Notify Discord when ETL orchestration completes, with best-candidate fallback"
executor_config: {}
executor_count: 1
executor_type: null
extensions: {}
name: notify_pipeline_completion
notification_config: {}
remote_variables_dir: null
retry_config: {}
run_pipeline_in_one_process: false
settings:
  triggers: null
spark_config: {}
tags: []
type: python
uuid: notify_pipeline_completion
variables_dir: /home/src/mage_data/default_repo
widgets: []
```

---

## 6. Discord Embed Examples

### Normal completion (with alerts)

```
✅ ETL Pipeline Run Complete

⏱ Duration: 3m 12s
📊 Pipelines:
  • market_discovery: success
  • wallet_discovery: success
  • position_sync: success
  • smart_money: success
🚨 Alerts Generated: 5
```

### Zero alerts — best candidate nominated

```
✅ ETL Pipeline Run Complete

⏱ Duration: 3m 15s
📊 Pipelines:
  • market_discovery: success
  • wallet_discovery: success
  • position_sync: success
  • smart_money: success
🚨 Alerts Generated: 0
🏆 Best Candidate (sub-threshold):
  Wallet: `0x1234...abcd`
  Action: NEW_POSITION
  Score: 72 (required ≥ 80)
  Position Size: $4,200.00
  Market: Will candidate X win?
```

---

## Pipeline SLA

| Metric | Target |
|---|---|
| Notification latency (post-pipeline) | < 5s |
| Best-candidate query time | < 200ms |
| Discord delivery success rate | ≥ 99% |

---

## Files to Create / Modify

| Action | Path |
|---|---|
| CREATE | `magic/default_repo/data_exporters/notify_pipeline_completion.py` |
| CREATE | `magic/default_repo/transformers/nominate_best_candidate.py` (optional — for standalone reuse) |
| EDIT | `magic/default_repo/pipelines/orchestration/metadata.yaml` — add `notify_pipeline_completion` block + wire downstream |
| EDIT | `docker-compose.yml` — add `DISCORD_WEBHOOK_URL` to `mage` service environment |
