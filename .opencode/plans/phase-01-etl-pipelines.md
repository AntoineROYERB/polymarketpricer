# Phase 1 — ETL Pipelines

> **Goal**: Implement 6 Mage AI pipelines to feed the database.
> **Schema ref**: `.opencode/plans/phase-01-database-redesign.md`
> **Status**: Planning — ready for implementation.

---

## Environment

- Mage container connects to `postgresql://app:devpassword@postgres:5432/polymarket`
- Each block uses SQLAlchemy with inline model definitions (opt B)
- PostgreSQL connection in each exporter:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("postgresql://app:devpassword@postgres:5432/polymarket")
Session = sessionmaker(bind=engine)
```

---

## Pipeline 1: `market_discovery` (daily `0 6 * * *`)

Fetch active + resolved markets from Gamma API.

### Blocks

| Name | Type | Details |
|---|---|---|
| `load_active_markets` | Data Loader | `GET /events?closed=false&limit=100` → paginate → for each event `GET /markets?event={id}` → collect |
| `load_resolved_markets` | Data Loader | `GET /events?closed=true&limit=100` → same pagination |
| `merge_markets` | Transformer | Deduplicate by market ID. Flatten event metadata. Separate outcomes into `outcomes` table data |
| `export_markets` | Data Exporter | Upsert `events`, `markets`, `outcomes` tables |

### Tables written

- `events`: id, title, slug, category, start_date, end_date, closed
- `markets`: id, question, category, event_id, event_slug, volume_usd, liquidity_usd, close_time, created_at, resolved_at, winning_outcome
- `outcomes`: id, market_id, label, price, winner

### Upsert patterns

```sql
INSERT INTO events (...) VALUES (...) ON CONFLICT (id) DO UPDATE SET ...;
INSERT INTO markets (...) VALUES (...) ON CONFLICT (id) DO UPDATE SET ...;
INSERT INTO outcomes (...) VALUES (...) ON CONFLICT (id) DO UPDATE SET ...;
```

---

## Pipeline 2: `wallet_discovery` (daily `0 7 * * *`)

Discover wallets from active markets.

### Blocks

| Name | Type | Details |
|---|---|---|
| `load_holders_for_active_markets` | Data Loader | `GET /holders?market={market_id}` (Data API) → collect unique addresses |
| `resolve_proxy_wallets` | Data Loader | `GET /users/{address}` (Gamma) → extract proxy_wallet mapping |
| `build_wallet_records` | Transformer | Build wallet rows, set first_seen/last_seen |
| `export_wallets` | Data Exporter | Upsert `wallets` |

### Tables written

- `wallets`: wallet, main_wallet, is_tracked (default True), first_seen, last_seen, last_position_sync, last_trade_sync

### Rate limits

- `/holders` (Data API): 1k/10s → 400ms spacing
- `/users` (Gamma): 4k/10s → can batch more aggressively

---

## Pipeline 3: `position_sync` (every 60s `*/1 * * * *`)

Near-real-time positions for all tracked wallets.

### Blocks

| Name | Type | Details |
|---|---|---|
| `load_tracked_wallets` | Data Loader | `SELECT wallet, main_wallet FROM wallets WHERE is_tracked = true` |
| `load_positions` | Data Loader | For each proxy wallet → `GET /positions?user={proxy_wallet}` (Data API, 150/10s limit). Batch 150 requests per 10s window |
| `merge_positions` | Transformer | Detect changes from previous state. Build `position_history` rows for deltas. Set entry_time on new positions, exit_time on closed |
| `export_positions` | Data Exporter | Upsert `positions`, insert `position_history` rows |

### Tables written

- `positions` (upsert): wallet, market_id, outcome_id, side, status, avg_entry_price, shares, entry_time, exit_time, realized_pnl, unrealized_pnl, total_pnl
- `position_history` (insert): wallet, market_id, outcome_id, side, shares_before, shares_after, pnl_change, recorded_at

### Position change detection logic

| Previous state | New state | Action |
|---|---|---|
| No row exists | Position returned | Set `status=OPEN`, `entry_time=now()` |
| Shares changed | Same position | Log delta to `position_history`, update shares/pnl |
| Position existed | No longer returned | Set `status=CLOSED`, `exit_time=now()` |
| Market resolved | Outcome matched | Set `status=RESOLVED` |

---

## Pipeline 4: `trade_history` (daily `0 8 * * *`)

Fetch trade history with cursor pagination.

### Blocks

| Name | Type | Details |
|---|---|---|
| `load_tracked_wallets_for_trades` | Data Loader | `SELECT wallet, main_wallet FROM wallets WHERE is_tracked = true` |
| `load_trades_for_wallet` | Data Loader | `GET /trades?user={proxy_wallet}&limit=500` (Data API) → paginate with cursor. Stop when hitting a timestamp already in DB (incremental) |
| `deduplicate_trades` | Transformer | Remove duplicates by trade ID |
| `export_trades` | Data Exporter | `INSERT INTO trades (...) VALUES (...) ON CONFLICT (id) DO NOTHING` |

### Tables written

- `trades`: id, wallet, market_id, outcome_id, side (BUY/SELL), type (MARKET/LIMIT), price, shares, amount_usd, fee_usd, timestamp, tx_hash

### Initial backfill

Run manually once with `backfill=True`. Fetch all historical trades (no cursor stop). Large — may take hours.

---

## Pipeline 5: `analytics_computation` (daily `30 8 * * *`)

Compute wallet metrics from trades and positions.

### Blocks

| Name | Type | Details |
|---|---|---|
| `load_recent_activity` | Data Loader | `SELECT DISTINCT wallet FROM trades WHERE timestamp >= CURRENT_DATE - 1` |
| `load_positions_data` | Data Loader | SQL read: `SELECT * FROM positions WHERE wallet IN :wallets` |
| `load_trades_data` | Data Loader | SQL read: `SELECT * FROM trades WHERE wallet IN :wallets` |
| `compute_wallet_metrics` | Transformer | For each wallet, compute all analytics fields |
| `export_analytics` | Data Exporter | `INSERT INTO wallet_analytics (...) VALUES (...) ON CONFLICT (wallet, snapshot_date) DO UPDATE SET ...` |

### Tables written

- `wallet_analytics`: wallet, snapshot_date, total_pnl, total_realized_pnl, total_unrealized_pnl, roi, total_volume, total_cost_basis, win_rate, num_trades, num_resolved_positions, profit_factor, sharpe_ratio, max_drawdown, avg_position_size, avg_holding_duration, consistency_score, experience_score, wallet_score

### Metric formulas

| Metric | Formula |
|---|---|
| `total_pnl` | `SUM(realized_pnl)` + `SUM(unrealized_pnl)` |
| `total_realized_pnl` | `SUM(realized_pnl)` from closed positions |
| `total_unrealized_pnl` | `SUM(unrealized_pnl)` from open positions |
| `roi` | `total_pnl / total_cost_basis * 100` |
| `total_volume` | `SUM(ABS(amount_usd))` from trades |
| `total_cost_basis` | `SUM(price * shares)` for BUY trades + `SUM(price * shares)` for SELL trades (absolute) |
| `win_rate` | `COUNT(resolved positions WHERE realized_pnl > 0) / COUNT(total resolved positions)` |
| `num_resolved_positions` | `COUNT(positions WHERE status = 'RESOLVED' OR status = 'CLOSED')` |
| `profit_factor` | `SUM(realized_pnl WHERE > 0) / ABS(SUM(realized_pnl WHERE < 0))` |
| `sharpe_ratio` | `AVG(trade_pnl) / STDDEV(trade_pnl) * SQRT(252)` — only if num_trades >= 10 |
| `max_drawdown` | Max peak-to-trough decline of cumulative PnL over time |
| `avg_position_size` | `AVG(trades.amount_usd)` |
| `avg_holding_duration` | `AVG(exit_time - entry_time)` for closed/resolved positions |
| `consistency_score` | `1 / (1 + STDDEV(total_pnl))` across last N daily snapshots |
| `experience_score` | `LN(num_trades) / LN(MAX(num_trades across all wallets))` |

---

## Pipeline 6: `ranking_computation` (every 6h `0 */6 * * *`)

Score wallets and materialize leaderboard.

### Blocks

| Name | Type | Details |
|---|---|---|
| `load_all_analytics` | Data Loader | SQL read: `SELECT * FROM wallet_analytics WHERE snapshot_date = CURRENT_DATE` |
| `load_wallet_metadata` | Data Loader | SQL read: `SELECT wallet, first_seen FROM wallets` |
| `filter_eligible_wallets` | Transformer | Remove wallets not meeting: `num_trades >= 50`, `total_volume >= 1000`, `age >= 3 months` |
| `compute_consistency_score` | Transformer | Already computed in analytics — use from `wallet_analytics` |
| `compute_experience_score` | Transformer | Already computed in analytics — use from `wallet_analytics` |
| `compute_wallet_scores` | Transformer | Normalize and compute weighted score |
| `materialize_rankings` | Data Exporter | Delete old snapshots, insert new ones. Update `wallet_analytics.wallet_score` |

### Tables written

- `ranking_snapshots`: wallet, snapshot_date, list_type, rank, wallet_score, roi, win_rate, consistency_score, experience_score, risk_adj_return, total_pnl, num_trades
- `wallet_analytics.wallet_score` updated for current date

### Weighted score formula

```python
wallet_score = (
    0.35 * norm_roi +
    0.25 * norm_winrate +
    0.15 * consistency_score +
    0.15 * experience_score +
    0.10 * norm_sharpe
)
```

Normalization: `(x - min) / (max - min)` across eligible set. If max == min, score = 0.5.

### List materialization

| List | Filter | Count |
|---|---|---|
| `top_100` | Eligible wallets, highest score | 100 |
| `emerging` | Wallets with 3–6 months age, highest score | 10 |
| `consistent` | All eligible, highest consistency_score | 10 |

---

## Pipeline Dependencies

```
market_discovery ──> wallet_discovery ──> position_sync (continuous)
                                         └──> trade_history ──> analytics_computation ──> ranking_computation
```

---

## Infrastructure

- `mage/Dockerfile` builds from `mageai/mageai:latest` with `psycopg2-binary sqlalchemy pandas requests`
- Pipelines registered via Mage UI (Triggers tab) or by writing `pipelines/<name>/metadata.yaml` files
- All pipelines follow: `data_loader → transformer → data_exporter`
