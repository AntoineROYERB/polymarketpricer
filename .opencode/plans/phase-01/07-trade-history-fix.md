# Fix ingestion_trade_history Pipeline

## Result

✅ **Pipeline terminée** — 184 196 trades exportés en 202s.

## Problem (original)

`load_trades_for_wallet.py` returned 0 trades because:

1. **Wrong API**: Called `gamma-api.polymarket.com/trades` — Gamma API does NOT expose a `/trades` endpoint.
2. **Wrong pagination**: Used cursor-based pagination; Data API uses offset-based (`offset` + `limit`).
3. **No concurrency**: Sequential loop over 3,901 wallets (~20 min).
4. **Timestamp type**: Data API returns Unix seconds (integer), DB expects `timestamptz`.
5. **Missing `amount_usd`**: Data API doesn't return it — computed as `size * price`.
6. **No unique trade ID**: Data API has no `id` field — constructed as `{txHash}-{asset}`.
7. **Unknown conditionIds**: ~85% of trades reference markets not in DB — filtered out.

## Changes applied

### `load_trades_for_wallet.py`

```
GAMMA_API → DATA_API  ("https://data-api.polymarket.com")
```

**Pagination**: cursor → offset (`limit` + `offset` params).

**Concurrency**: `ThreadPoolExecutor(max_workers=10)` — same pattern as `load_positions.py`.

**Field mapping fixes**:
- `market_id`: lookup via `conditionId` → `markets.condition_id` (was using `t.get("market")` which returns `None`)
- `id`: composite `{transactionHash}-{asset}` (Data API has no unique trade ID)
- `timestamp`: `datetime.fromtimestamp(int(ts), tz=timezone.utc)` (was passing raw Unix int)
- `amount_usd`: `size * price` (Data API doesn't return amount)
- `outcome_id`: raw `asset` token ID from Data API

**Data filtering**: skip trades whose `conditionId` is not in `markets` table (avoids NOT NULL violation on `market_id`).

### `export_trades.py`

No changes needed — the loader now produces all required columns in the expected format.

### Database

Dropped `trades_outcome_id_fkey` — Data API returns token IDs (`asset`) that don't match `outcomes.id`. Same approach as `positions_outcome_id_fkey`.

## Remaining trades skipped (~85%)

Expected: market discovery only captures active + recently resolved markets. Trades on older/unresolved markets are silently dropped. Analytics pipelines only need trades for known markets, so this is safe.

## Verification

```bash
docker compose exec mage python /home/src/scripts/run_all.py ingestion_trade_history
docker compose exec postgres psql -U app -d polymarket -c "SELECT COUNT(*) FROM trades"
```

**Result**: `COUNT(*) = 184196`

## Next

- Run `enrichment_analytics_computation` and `enrichment_ranking_computation` pipelines
- Refresh seed dump
