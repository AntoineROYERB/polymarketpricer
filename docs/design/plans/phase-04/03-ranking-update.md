# Phase 4 — Edge Scoring — Ranking Update

> **Goal**: Update the `enrichment_ranking_computation` pipeline to read `edge_score` from `wallet_edge_snapshots` and incorporate it into the weighted ranking formula.
> **AI Agent Instructions**: Modify the existing Mage AI pipeline `enrichment_ranking_computation` — update its data loader to LEFT JOIN `wallet_edge_snapshots`, and update the scoring formula in the transformer.

---

## Current Formula (Phase 1–3)

```
wallet_score = 0.25*roi + 0.25*consistency + 0.20*experience + 0.15*risk_adj_return + 0.15*volume
```

## New Formula (Phase 4)

```
wallet_score = 0.40*edge_score + 0.20*consistency + 0.20*roi + 0.10*experience + 0.10*risk_adj_return
```

### Changes

| Component | Old Weight | New Weight | Source |
|-----------|-----------|-----------|--------|
| `edge_score` | — | **0.40** | `wallet_edge_snapshots.edge_score` (NEW) |
| `consistency` | 0.25 | 0.20 | `wallet_analytics` |
| `roi` | 0.25 | 0.20 | `wallet_analytics` |
| `experience` | 0.20 | 0.10 | `wallet_analytics` |
| `risk_adj_return` | 0.15 | 0.10 | `wallet_analytics` |
| `volume` | 0.15 | **removed** | Replaced by edge_score |

### Rationale for Weight Changes

- **edge_score (0.40)** is the most predictive signal of future performance — it measures actual prediction accuracy (ROI per trade on resolved markets), not just volume or activity.
- **consistency (0.20)** and **roi (0.20)** remain important but are demoted to make room for edge.
- **experience (0.10)** and **risk_adj_return (0.10)** have lower predictive power and are reduced accordingly.
- **volume (0.15)** is removed entirely — volume without edge is noise (a wallet can trade large amounts with zero predictive skill). Volume's influence is now indirectly captured through `num_edge_trades`.

---

## Required Changes

### 1. Data Loader: Update SQL Query

Modify `magic/default_repo/data_loaders/load_wallet_analytics.py` to LEFT JOIN `wallet_edge_snapshots`:

```sql
SELECT
    wa.wallet,
    wa.snapshot_date,
    wa.roi,
    wa.consistency,
    wa.experience,
    wa.risk_adj_return,
    -- Phase 4: edge_score from wallet_edge_snapshots
    COALESCE(wes.edge_score, 0) AS edge_score,
    COALESCE(wes.edge_consistency, 0) AS edge_consistency,
    COALESCE(wes.num_edge_trades, 0) AS num_edge_trades
FROM wallet_analytics wa
LEFT JOIN (
    -- Get most recent edge snapshot per wallet
    SELECT DISTINCT ON (wallet)
        wallet, edge_score, edge_consistency, num_edge_trades
    FROM wallet_edge_snapshots
    ORDER BY wallet, snapshot_date DESC
) wes ON wes.wallet = wa.wallet
WHERE wa.snapshot_date = CURRENT_DATE
```

This ensures:
- Wallets without edge data still get a score (edge_score = 0 fallback).
- The most recent edge snapshot is used.
- Edge data is optional — the ranking pipeline still works if edge scoring hasn't run yet.

### 2. Transformer: Update Scoring Formula

Modify `magic/default_repo/transformers/compute_wallet_metrics.py` (or the equivalent transformer in the ranking pipeline).

**Old formula:**

```python
wallet_score = (
    0.25 * float(row["roi"])
    + 0.25 * float(row["consistency"])
    + 0.20 * float(row["experience"])
    + 0.15 * float(row["risk_adj_return"])
    + 0.15 * float(row["volume"])
)
```

**New formula:**

```python
wallet_score = (
    0.40 * float(row.get("edge_score", 0))
    + 0.20 * float(row["consistency"])
    + 0.20 * float(row["roi"])
    + 0.10 * float(row["experience"])
    + 0.10 * float(row.get("risk_adj_return", 0))
)
```

### 3. Data Exporter: Update Write Columns

Modify `magic/default_repo/data_exporters/export_ranking_snapshots.py` to include `edge_score` in the rows written to `ranking_snapshots`:

```python
INSERT INTO ranking_snapshots
    (wallet, snapshot_date, rank, wallet_score, roi, consistency,
     experience, risk_adj_return, volume, edge_score)
VALUES
    (:wallet, :snapshot_date, :rank, :wallet_score, :roi, :consistency,
     :experience, :risk_adj_return, :volume, :edge_score)
ON CONFLICT (wallet, snapshot_date)
DO UPDATE SET
    wallet_score = EXCLUDED.wallet_score,
    edge_score = EXCLUDED.edge_score,
    ...
```

---

## Edge Score Normalisation

The `edge_score` in `wallet_edge_snapshots` is already normalised to [0, 1] via min-max scaling during the `enrichment_edge_scoring` pipeline. No further normalisation is needed in the ranking pipeline.

### Handling Missing Edge Data

| Case | edge_score value | Impact on ranking |
|------|-----------------|-------------------|
| Wallet has edge data | 0.0 – 1.0 | Full formula applies |
| Wallet has 0 trades on resolved markets | 0.0 (fallback) | Wallet ranks lower — penalised fairly |
| Edge pipeline hasn't run yet | 0.0 (fallback) | Ranking works but edge dimension is missing |
| Edge pipeline errors | 0.0 (fallback) | No crash — uses last known or zero |

---

## Files to Modify

| Action | Path | Change |
|--------|------|--------|
| EDIT | `magic/default_repo/data_loaders/load_wallet_analytics.py` | Add LEFT JOIN to `wallet_edge_snapshots` |
| EDIT | `magic/default_repo/transformers/compute_wallet_metrics.py` | Apply new ranking formula |
| EDIT | `magic/default_repo/data_exporters/export_ranking_snapshots.py` | Include `edge_score` column in UPSERT |

---

## Verification

```bash
# Run the edge scoring pipeline first
docker compose exec mage mage run /home/src/default_repo enrichment_edge_scoring

# Run the ranking pipeline and verify new formula
docker compose exec mage mage run /home/src/default_repo enrichment_ranking_computation

# Check that edge_score appears in ranking_snapshots
psql -U app -d polymarket -c "
    SELECT wallet, rank, wallet_score, edge_score
    FROM ranking_snapshots
    WHERE snapshot_date = CURRENT_DATE
    ORDER BY rank
    LIMIT 20;
"

# Verify edge_score contributes ~40% to wallet_score
psql -U app -d polymarket -c "
    SELECT wallet, wallet_score, edge_score,
           ROUND((edge_score::numeric / NULLIF(wallet_score::numeric, 0)) * 100, 1) AS edge_pct
    FROM ranking_snapshots
    WHERE snapshot_date = CURRENT_DATE
      AND edge_score > 0
    ORDER BY rank
    LIMIT 10;
"
```

---

## Backward Compatibility

| Concern | Mitigation |
|---------|-----------|
| Existing `ranking_snapshots` rows missing `edge_score` | `edge_score` column added as nullable — old rows have NULL |
| Dashboard or API reading old rank data | Old data unaffected; new daily snapshots include edge_score |
| Tests expecting old formula | Update integration test thresholds and mock data |
| `volume` column still exists in `wallet_analytics` | Column kept for historical reference, removed only from formula |
