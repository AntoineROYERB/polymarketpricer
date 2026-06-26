# Phase 4 — Edge Scoring — Sign-off Checklist

> **Objective**: Track completion of all Phase 4 deliverables before starting Phase 5.
> **Status**: ❌ Pending
> **Version**: v0.4.0

## Phase Description

**Edge Scoring** — computes the predictive accuracy of each wallet by measuring ROI per trade on resolved markets (edge). Incorporates edge_score into the ranking formula (40% weight) and exposes edge metrics via dedicated API endpoints.

### What this phase delivers

- Migration `008_add_edge_scoring.py` — `wallet_edge_snapshots` table + `edge_score` columns on `wallet_analytics` and `ranking_snapshots`
- `enrichment_edge_scoring` ETL pipeline — load resolved trades, compute edge per trade (FIFO matching), aggregate into per-wallet snapshots
- Update to `enrichment_ranking_computation` — new formula: `0.40*edge_score + 0.20*consistency + 0.20*roi + 0.10*experience + 0.10*risk_adj_return`
- `GET /api/v1/leaderboard/edge` — rankings by edge_score
- `GET /api/v1/wallets/{address}/edge` — detailed edge metrics per wallet
- Update existing endpoints — `GET /api/v1/leaderboard` and `GET /api/v1/wallets/{address}` include edge data
- ~25 new tests (10 unit + 6 API + 9 integration)

### What this phase does NOT cover

> - Partial share matching (one BUY partially closed by multiple SELLs) — deferred; MVP assumes one SELL fully closes a position
> - Edge computation for non-resolved markets — deferred; markets must resolve for ground truth
> - Real-time edge updates — deferred; daily snapshot sufficient for MVP
> - Historical backfill of edge snapshots — deferred; pipeline computes from all historical resolved trades

---

## Deliverables Overview

| # | Feature | Plan File | Est. Complexity |
|---|---|---|---|
| 1 | Database schema | `./01-database-schema.md` | Medium |
| 2 | Edge scoring pipeline | `./02-edge-scoring-pipeline.md` | High |
| 3 | Ranking update | `./03-ranking-update.md` | Medium |
| 4 | API endpoints | `./04-api-endpoints.md` | Medium |
| 5 | Testing | `./05-testing.md` | Medium |

---

## Detailed Checklist

### 1. Database Schema

- [ ] Migration `008_add_edge_scoring.py` created
- [ ] `wallet_edge_snapshots` table: wallet, snapshot_date, avg_edge, median_edge, edge_consistency, edge_volatility, edge_score, num_edge_trades, positive_edge_trades, negative_edge_trades, computed_at
- [ ] Foreign key: `wallet_edge_snapshots.wallet` → `wallets.wallet`
- [ ] Composite PK: (wallet, snapshot_date)
- [ ] Indexes: wallet+snapshot_date DESC, snapshot_date DESC, edge_score DESC
- [ ] `edge_score numeric(8,6)` added to `wallet_analytics`
- [ ] `edge_score numeric(8,6)` added to `ranking_snapshots`
- [ ] SQLAlchemy model `WalletEdgeSnapshot` in `app/db/models.py`
- [ ] `edge_score` column added to `WalletAnalytic` and `RankingSnapshot` models
- [ ] Pydantic schemas `WalletEdgeSnapshot`, `EdgeLeaderboardEntry`, `EdgeLeaderboardResponse` in `app/models/schemas.py`
- [ ] `LeaderboardEntry` updated with `edge_score`, `edge_consistency`, `num_edge_trades`
- [ ] `WalletDetail` updated with `edge_metrics`
- [ ] Downgrade works cleanly (drops columns + table)
- [ ] Existing Phase 1–3 data intact after migration

### 2. Edge Scoring Pipeline

- [ ] `enrichment_edge_scoring` pipeline created in Mage AI
- [ ] Data loader `load_resolved_trades.py` — PG query for all trades on resolved markets
- [ ] Data loader `load_trade_outcomes.py` — PG query for outcomes with winner flag
- [ ] Transformer `compute_trade_edge.py` — implements edge algorithm:
  - [ ] BUY → SELL matching (FIFO)
  - [ ] BUY → resolution price (1.0/0.0) if held to resolution
  - [ ] SELL without BUY → ignored
  - [ ] Edge = 0 → counted as negative in consistency
  - [ ] Per-trade edge computation (no weighted average)
  - [ ] Aggregation per wallet (avg, median, consistency, volatility)
  - [ ] Min-max normalisation of avg_edge into [0, 1] edge_score
- [ ] Data exporter `export_edge_snapshots.py` — UPSERT into `wallet_edge_snapshots`
- [ ] Pipeline registered in orchestration (after `trigger_category_analytics`, before `trigger_ranking`)
- [ ] `trigger_edge_scoring.py` exporter created
- [ ] Pipeline completes within 5 min SLA
- [ ] Existing 11 pipelines still run correctly

### 3. Ranking Update

- [ ] Data loader `load_wallet_analytics.py` updated with LEFT JOIN to `wallet_edge_snapshots`
- [ ] Transformer `compute_wallet_metrics.py` applies new formula:
  - [ ] `0.40*edge_score + 0.20*consistency + 0.20*roi + 0.10*experience + 0.10*risk_adj_return`
- [ ] Missing edge_score defaults to 0.0 (no crash)
- [ ] Data exporter `export_ranking_snapshots.py` includes `edge_score` column
- [ ] `volume` weight removed from formula (replaced by edge_score)
- [ ] Ranking pipeline produces correct scores after edge scoring runs

### 4. API Endpoints

- [ ] `GET /api/v1/leaderboard/edge` — ranked by edge_score DESC
  - [ ] Pagination (limit/offset)
  - [ ] Input validation (422 for invalid params)
  - [ ] Response includes rank, edge_score, avg_edge, edge_consistency, num_edge_trades
- [ ] `GET /api/v1/wallets/{address}/edge` — detailed edge metrics
  - [ ] 404 for unknown wallet
  - [ ] Graceful response when wallet has no edge data
- [ ] `GET /api/v1/leaderboard` — updated with `edge_score`, `edge_consistency`, `num_edge_trades`
- [ ] `GET /api/v1/wallets/{address}` — updated with `edge_metrics` object
- [ ] All response models use Pydantic schemas
- [ ] Router registered in `app/api/router.py`

### 5. Testing

- [ ] ~10 unit tests for edge computation (`test_edge_scoring.py`):
  - [ ] BUY held to resolution (win)
  - [ ] BUY held to resolution (loss)
  - [ ] BUY then SELL before resolution
  - [ ] Multiple BUYs with FIFO matching
  - [ ] Edge = 0 counted as negative
  - [ ] SELL without BUY ignored
  - [ ] Zero entry price skipped
  - [ ] Aggregation correctness (avg, consistency, volatility)
  - [ ] Min-max normalisation
  - [ ] Empty trades edge case
- [ ] ~6 API tests for edge endpoints (`test_api/test_edge_endpoints.py`):
  - [ ] Edge leaderboard empty
  - [ ] Edge leaderboard with data
  - [ ] Edge leaderboard pagination
  - [ ] Edge leaderboard invalid params
  - [ ] Wallet edge success
  - [ ] Wallet edge not found (404)
- [ ] ~9 integration tests in `test_db_integrity.py`:
  - [ ] Table queryable
  - [ ] FK integrity (wallet)
  - [ ] NOT NULL constraints (wallet, snapshot_date, avg_edge, num_edge_trades)
  - [ ] edge_score in [0, 1]
  - [ ] edge_consistency in [0, 1]
  - [ ] edge_volatility >= 0
  - [ ] avg_edge within bounds
  - [ ] edge_score column exists in wallet_analytics
  - [ ] edge_score column exists in ranking_snapshots
- [ ] ROW_THRESHOLDS updated with `wallet_edge_snapshots: 50`
- [ ] All tests pass
- [ ] Migration forward + backward verified (008)
- [ ] No regression on existing tests (~149 → ~174 total)

### 6. Documentation

- [ ] AGENTS.md updated with `enrichment_edge_scoring` pipeline
- [ ] CHANGELOG.md updated (v0.3.0 → v0.4.0)
- [ ] Architecture diagram updated (12 pipelines, edge scoring flow)
- [ ] This sign-off checklist completed

### 7. Infrastructure

- [ ] Seed dump refreshed after pipeline run
- [ ] All CI jobs pass (lint, api-tests, integration-tests)
- [ ] MyPy strict — 0 errors

---

## Blocker Tracking

| Priority | Blocker | Resolved | Notes |
|----------|---------|----------|-------|
| 🟡 Medium | FIFO partial share matching | ⏳ Deferred | MVP assumes full close; revisit if data shows frequent partial exits |
| 🟢 Low | Edge computation performance on large trade history | ⏳ Monitor | May need batching for wallets with > 1000 trades |
| 🟢 Low | Min-max normalisation dynamic range | ⏳ Monitor | Edge range depends on wallet distribution; outliers may compress scores |
| 🟢 Low | `volume` removed from ranking formula | ✅ Confirmed | Decision validated; volume without edge is noise |

---

## Release Procedure (Data Pipeline Only)

```bash
# 1. Run all migrations
alembic upgrade head

# 2. Run full test suite
python -m pytest app/tests/ -v

# 3. Lint and type-check
ruff check app/ && mypy app/ --strict

# 4. Run all pipelines incl. enrichment_edge_scoring
./scripts/run-all-pipelines.sh

# 5. Verify edge data
psql -U app -d polymarket -c "SELECT COUNT(*) FROM wallet_edge_snapshots;"
psql -U app -d polymarket -c "
    SELECT wallet, edge_score, avg_edge, num_edge_trades
    FROM wallet_edge_snapshots
    ORDER BY edge_score DESC
    LIMIT 10;
"

# 6. Verify new ranking formula
psql -U app -d polymarket -c "
    SELECT wallet, wallet_score, edge_score,
           ROUND((edge_score::numeric / NULLIF(wallet_score::numeric, 0)) * 100, 1) AS edge_pct
    FROM ranking_snapshots
    WHERE snapshot_date = CURRENT_DATE
      AND edge_score > 0
    ORDER BY rank
    LIMIT 10;
"

# 7. Test API endpoints
curl "http://localhost:8000/api/v1/leaderboard/edge?limit=5"
curl "http://localhost:8000/api/v1/wallets/0x1234...abcd/edge"

# 8. Refresh seed dump (optional but recommended)
./scripts/refresh-seed.sh
git add docker/initdb/seed.sql

# 9. Stage and commit
git add -A
git commit -m "feat: Phase 4 — Edge Scoring"

# 10. Tag & push
git tag -a v0.4.0 -m "Phase 4 — Edge Scoring"
git push origin v0.4.0

# 11. Mark Phase 4 progress in ROADMAP.md
```
