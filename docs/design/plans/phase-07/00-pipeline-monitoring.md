# Phase 7 — Pipeline Monitoring & Discord Alerting

> **Goal**: Detect ETL pipeline failures in real-time and send Discord alerts, so you're
> notified immediately when a pipeline crashes — without modifying any Mage pipeline blocks.
> **AI Agent Instructions**: Add a background monitoring loop to `app/main.py` that polls
> `pipeline_run_log` for failures and posts to Discord.
> **Status**: 🚧 In progress

---

## Why this approach?

Three options were considered:

| Option | Impact | Verdict |
|--------|--------|---------|
| Modify 12 `trigger_*.py` blocks | Changes 12+ files, duplicated logic | ❌ Fragile |
| Modify `notify_pipeline_completion.py` | Never runs if upstream pipeline fails | ❌ Doesn't work |
| **FastAPI background loop** | One file changed (`app/main.py`), zero Mage changes | ✅ Optimal |

The FastAPI app already has the DB connection, the Discord webhook URL, and async HTTP —
everything needed, already wired.

---

## How it works

1. Mage writes to `pipeline_run_log` on failure — already happens today via `record_status()`
2. A new async background loop in `app/main.py` polls the table every 5 minutes
3. On detecting a new failure, it posts a Discord alert via the existing webhook
4. An in-memory timestamp prevents duplicate notifications

---

## Files to modify

### 1. `app/main.py` — new background loop + wire into lifespan

Add a new async function before the existing loops:

```python
async def monitor_pipeline_failures_loop() -> None:
    """Poll pipeline_run_log every 5min and alert Discord on failures."""
    last_check = datetime.now(timezone.utc)
    while True:
        await asyncio.sleep(300)  # 5 minutes
        try:
            async with async_session() as db:
                result = await db.execute(
                    text("""
                        SELECT pipeline_name, status, updated_at
                        FROM pipeline_run_log
                        WHERE status != 'success'
                          AND updated_at > :last_check
                        ORDER BY updated_at
                    """),
                    {"last_check": last_check},
                )
                failures = result.all()
                if not failures:
                    continue

                lines = []
                for row in failures:
                    m = row._mapping
                    lines.append(
                        f"**{m['pipeline_name']}** — `{m['status']}` ({m['updated_at'].isoformat()})"
                    )
                payload = {"content": "🚨 **ETL Pipeline Failure**\n" + "\n".join(lines)}

                if settings.discord_webhook_url:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(settings.discord_webhook_url, json=payload)
                        if resp.status_code not in (200, 204):
                            logger.warning("Discord webhook returned %s", resp.status_code)

                last_check = datetime.now(timezone.utc)
        except Exception:
            logger.exception("Pipeline monitor error")
```

Register in `lifespan()` — add alongside existing tasks:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    delivery_task = asyncio.create_task(alert_delivery_loop())
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    paper_trade_task = asyncio.create_task(paper_trade_generation_loop())
    monitor_task = asyncio.create_task(monitor_pipeline_failures_loop())   # ← ADD
    yield
    delivery_task.cancel()
    heartbeat_task.cancel()
    paper_trade_task.cancel()
    monitor_task.cancel()                                                  # ← ADD
```

---

## Changes Summary

| File | Change |
|------|--------|
| `app/main.py` | + ~35 lines: new loop + wiring in lifespan |
| Any Mage file | **None** |
| `docker-compose.yml` | **None** |
| `.env` | **None** |

---

## Discord message example

> 🚨 **ETL Pipeline Failure**
> **ingestion_wallet_discovery** — `failed: HTTP 429 rate limited` (2026-07-06T14:30:00+00:00)
> **enrichment_analytics_computation** — `failed: division by zero` (2026-07-06T14:32:00+00:00)

---

## Testing

### Manual test (no need to break a real pipeline):

```bash
# Inject a fake failure into pipeline_run_log
docker compose exec postgres psql -U app -d polymarket -c "
INSERT INTO pipeline_run_log (pipeline_name, status, updated_at)
VALUES ('test_failure', 'failed: intentional test', NOW());
"
```

Wait up to 5 minutes → check Discord for the alert.

Then clean up:
```bash
docker compose exec postgres psql -U app -d polymarket -c "
DELETE FROM pipeline_run_log WHERE pipeline_name = 'test_failure';
"
```

### Integration test (optional, future):

Extend `test_db_integrity.py` with a test that:
1. Inserts a fake failure row
2. Calls the monitor logic directly
3. Asserts a webhook call was made

---

## Future improvements

| Priority | Improvement |
|----------|-------------|
| 🟡 Medium | Add `notified_at` column to `pipeline_run_log` for persistent dedup |
| 🟢 Low | Embed block-level error from Mage SQLite DB in the alert |
| 🟢 Low | Expose `GET /api/v1/monitor/pipeline-status` endpoint |
| 🟢 Low | Batch alerts into a single daily digest for non-critical failures |

---

## Rollback

If the monitoring loop causes issues, simply comment out the two lines in `lifespan()`:

```python
# monitor_task = asyncio.create_task(monitor_pipeline_failures_loop())
...
# monitor_task.cancel()
```

No data loss, no schema changes — zero-risk revert.
