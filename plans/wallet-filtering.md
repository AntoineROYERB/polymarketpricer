# Wallet Filtering

## Objective

Filter out low-quality wallets before computing analytics and rankings, as specified in the Phase 1 ROADMAP.

Wallets that do not meet minimum thresholds should be excluded from:
- `wallet_analytics` computation
- `ranking_snapshots` computation
- API leaderboard responses

---

## Filtering Rules (from ROADMAP)

Ignore wallets with:

| Rule | Threshold | Rationale |
|---|---|---|
| Minimum resolved trades | < 50 | Eliminates wallets with insufficient sample size |
| Minimum volume | < $1,000 | Eliminates wallets with negligible economic activity |
| Minimum history | < 3 months | Eliminates new wallets without proven track record |

---

## Current State

Without filtering, `wallet_analytics` contains **3,345 wallets**.
With filtering applied:

| Filter | Wallets passing | Wallets excluded |
|---|---|---|
| ≥ 50 resolved trades | ~1,183 | ~2,162 |
| ≥ $1,000 volume | ~1,020 | ~2,325 |
| ≥ 3 months history | TBD | TBD |

Applying all three filters would eliminate roughly **2/3 of wallets**, keeping only the most meaningful traders in the leaderboard.

---

## Implementation Options

### Option A — Filter at Analytics Stage (recommended)

Modify `compute_wallet_metrics.py` to skip wallets that don't meet thresholds.

**Pros:**
- Analytics table stays clean
- Less data stored
- Ranking automatically inherits the filter

**Cons:**
- Need access to position data (for resolved_trades count) before computing
- 3-month history needs `first_seen`/`last_seen` from wallets table

**Location:** `magic/default_repo/transformers/compute_wallet_metrics.py`

```python
# After computing metrics, apply filters before returning
def should_include(resolved_total, total_volume, first_seen):
    if resolved_total < 50:
        return False
    if total_volume < 1000:
        return False
    if first_seen and (today - first_seen).days < 90:
        return False
    return True
```

### Option B — Filter at Ranking Stage

Modify `compute_wallet_scores.py` to exclude filtered wallets before scoring.

**Pros:**
- Preserves all analytics data for future analysis
- No data loss

**Cons:**
- Analytics table still contains noisy wallets
- Duplicates filter logic in the scoring layer

### Option C — Filter in API Layer

Add query parameters to `/leaderboard` endpoints.

**Pros:**
- Most flexible — users can adjust thresholds
- No data changes needed

**Cons:**
- Does not satisfy ROADMAP requirement (filtering should be architectural, not cosmetic)
- Noisy data still flows through pipelines

---

## Data Needed

### Resolved trades count
Already computed as `num_resolved_positions` in `compute_wallet_metrics.py`.

### Total volume
Already computed as `total_volume` in `compute_wallet_metrics.py`.

### 3-month history
Needs `first_seen` timestamp per wallet. Available in `wallets` table.
Currently `wallets` has columns: `wallet`, `first_seen`, `last_seen`.

---

## Proposed Implementation (Option A)

1. In `compute_wallet_metrics.py`, add a `should_include` check after metrics computation
2. If wallet fails any filter, return `None` instead of the metrics dict
3. Filter out `None` rows before building the DataFrame
4. Ensure the `wallets` DataFrame is passed to the transformer for `first_seen` access

### Transformer signature change

Current:
```python
def transform_df(positions: DataFrame, trades: DataFrame, *args, **kwargs) -> DataFrame:
```

New:
```python
def transform_df(positions: DataFrame, trades: DataFrame, wallets: DataFrame, *args, **kwargs) -> DataFrame:
```

---

## Edge Cases

- **Wallets with 0 trades and 0 positions** — already handled (metrics will be 0/None, should be filtered)
- **Wallets created recently** — < 3 months history, excluded even if high volume
- **`first_seen` is NULL** — treat as failing the history check
- **`resolved_total` is 0** — fails the resolved_trades filter

---

## Test Plan

1. Add integration test: `test_wallet_filtering_excludes_low_quality`
2. Verify filtered wallets have `resolved_total < 50` or `total_volume < 1000`
3. Verify count of `wallet_analytics` drops after applying filter
4. Verify ranking excludes filtered wallets
