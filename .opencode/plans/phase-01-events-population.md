# Events Table Population

## Objective

Determine whether the `events` table should be populated for Phase 1, and if so, implement the population pipeline.

---

## Current State

- `events` table exists with full schema
- Contains **0 rows**
- `markets` table has a foreign key `event_id → events(id)`
- Integration test `test_empty_tables_stay_empty[events]` explicitly verifies the table is empty (PASSES)

### Events Schema

| Column | Type | Nullable |
|---|---|---|
| id | text | NOT NULL |
| title | text | NOT NULL |
| slug | text | ✅ |
| category | text | ✅ |
| start_date | timestamptz | ✅ |
| end_date | timestamptz | ✅ |
| closed | boolean | NOT NULL (default false) |

### Markets FK

```sql
CONSTRAINT "markets_event_id_fkey" FOREIGN KEY (event_id) REFERENCES events(id)
```

---

## Why Events Matter

The ROADMAP lists "Events" under Data Collection (Phase 1). Events are the parent container for markets (e.g., "US Election 2024" is an event containing multiple markets like "Will Candidate X win?").

Without events:
- Markets have `event_id` but no parent is resolvable
- Category-level analytics cannot group by event
- Phase 2 (Niche Expertise Detection) requires categories, which may come from events

---

## Options

### Option A — Populate Events Now (recommended for Phase 2 readiness)

Add an event discovery step to the `ingestion_market_discovery` pipeline.

**Gamma API:** The `/markets/keyset` endpoint may return `event_id` or `event_slug` per market. Events could be extracted and upserted from the market data.

**Implementation:**

1. In `ingestion_market_discovery`, after loading markets, extract unique events
2. Upsert into `events` table
3. Update the integration test: remove `events` from `EMPTY_TABLES`

### Option B — Leave Empty, Document Exclusion

Document that events are intentionally deferred to Phase 2.

Keep the integration test as-is (`events` is expected to be empty).

### Option C — Remove the FK or Make it Optional

If events are not used in Phase 1, consider making `event_id` nullable or deferring the FK constraint.

---

## Recommended Approach (Option A)

### Pipeline Changes

**File:** `magic/default_repo/pipelines/ingestion_market_discovery/`

1. Add a transformer step to extract events from the market payload
2. Upsert events before markets (to satisfy FK)
3. Update the data exporter to handle events

### Event Extraction Logic

```python
def extract_events(markets_df: DataFrame) -> DataFrame:
    """Extract unique events from market data."""
    events = []
    for _, market in markets_df.iterrows():
        event = {
            "id": market.get("event_id"),
            "title": market.get("event_title"),
            "slug": market.get("event_slug"),
            "category": market.get("category"),
            "start_date": market.get("event_start_date"),
            "end_date": market.get("event_end_date"),
            "closed": market.get("event_closed", False),
        }
        if event["id"]:
            events.append(event)
    return DataFrame(events).drop_duplicates(subset=["id"])
```

### Test Updates

- Remove `events` from `EMPTY_TABLES` in `test_db_integrity.py`
- Add row count test for `events` (if data available)
- Verify referential integrity: `markets.event_id → events.id`
