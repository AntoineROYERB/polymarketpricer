# Phase 5 — Follow & Paper Trading — Sign-off Checklist

> **Objective**: Track completion of all Phase 5 deliverables before starting Phase 6 (Dashboard).
> **Status**: 🚧 In progress
> **Version**: v0.5.0

## Phase Description

**Follow & Paper Trading** — allows users to follow top-performing wallets, receive enriched Discord alerts when they trade with copy suggestions, and automatically copy their trades in a simulated environment using real market prices with configurable virtual capital.

### Why this scope?

- **Bridging Phase 4 and Phase 5** — the follow recommendation engine (Phase 5 roadmap) needs a follow system and copy simulation to be meaningful. This phase builds the infrastructure.
- **Paper-first de-risking** — starting with fake money lets us validate the copy-trading mechanics, position tracking, and PnL simulation before any real-money integration.
- **User feedback loop** — the follow + alert + copy flow gives immediate value (Discord notifications with trade suggestions) while the simulation runs silently in the background.

### What this phase delivers

- 4 new database tables (`wallet_follows`, `paper_portfolios`, `paper_positions`, `paper_trades`) + `follow_score` on `wallet_analytics`
- Follow recommendation scoring (edge + consistency + category expertise + recency + frequency)
- Wallet follow CRUD API + recommendations endpoint
- Enhanced Discord alerts with wallet follow status and copy-trade suggestions
- Paper trading engine — auto-copy trades from followed wallets with configurable sizing (proportional or fixed), category filtering
- Portfolio API — overview, positions, trade history, manual close, portfolio reset
- ETL pipeline `enrichment_follow_scoring` + extension to `smart_money_detection` for paper trade generation
- ~40 new tests (unit + API + integration)

### What this phase does NOT cover

> - Real-money trading integration — deferred; Phase 5 is simulation-only
> - Multi-user authentication — deferred; single-user mode with `user_id` placeholder
> - Dashboard UI — deferred to Phase 6
> - Historical backfill of paper trades — deferred; paper portfolio starts empty on creation

---

## Deliverables Overview

| # | Feature | Plan File | Est. Complexity |
|---|---|---|---|
| 1 | Database schema | `./01-database-schema.md` | Medium |
| 2 | Follow recommendation scoring | `./02-follow-scoring.md` | Medium |
| 3 | Wallet follow API | `./03-follow-api.md` | Medium |
| 4 | Enhanced Discord alerts | `./04-enhanced-alerts.md` | Low |
| 5 | Paper trading engine | `./05-paper-trading-engine.md` | High |
| 6 | Portfolio API | `./06-portfolio-api.md` | Medium |
| 7 | ETL pipeline | `./07-etl-pipeline.md` | High |
| 8 | Testing | `./08-testing.md` | Medium |

---

## Detailed Checklist

### 1. Database Schema

- [ ] Migration `018_add_wallet_follows.py` — `wallet_follows` table
- [ ] Migration `019_add_paper_trading.py` — `paper_portfolios`, `paper_positions`, `paper_trades` tables
- [ ] Migration `020_add_follow_score.py` — `follow_score` column on `wallet_analytics`
- [ ] Foreign keys to `wallets.wallet`, `markets.id`, `alerts.id` (where applicable)
- [ ] Indexes on common query patterns (wallet, portfolio_id, status, detected_at)
- [ ] Composite PKs where appropriate
- [ ] SQLAlchemy models for all 4 new tables
- [ ] Pydantic schemas for all new models
- [ ] Downgrade works cleanly
- [ ] Existing Phase 1–4 data intact after migration

### 2. Follow Recommendation Scoring

- [ ] Formula implemented: `0.30*edge_score + 0.20*consistency + 0.20*category_specialization + 0.15*recency_decay + 0.15*trade_frequency`
- [ ] Category specialization score computed from category_analytics (is_specialist flag, category_rank)
- [ ] Recency decay based on days since last trade (exponential decay)
- [ ] Trade frequency score based on trades per month
- [ ] Missing data defaults to 0 (no crash)
- [ ] Normalised to [0, 1] range via min-max scaling
- [ ] Follow recommendations endpoint returns top-N wallets by follow_score

### 3. Wallet Follow API

- [ ] `GET /api/v1/follow/recommendations` — recommended wallets
- [ ] `GET /api/v1/follow` — list followed wallets with config
- [ ] `POST /api/v1/follow/{wallet}` — follow with body (label, auto_copy, copy_mode, copy_value, category_filter)
- [ ] `PATCH /api/v1/follow/{wallet}` — update follow settings
- [ ] `DELETE /api/v1/follow/{wallet}` — unfollow (soft delete)
- [ ] Input validation (422 for invalid params)
- [ ] Pagination where applicable
- [ ] 404 for unknown wallet
- [ ] Pydantic schemas for all request/response models

### 4. Enhanced Discord Alerts

- [ ] Detect if alert wallet is followed by user
- [ ] Add "You follow this trader" indicator in embed
- [ ] Add copy suggestion block (calculated amount, price)
- [ ] Add "Auto-copy: ON/OFF" status
- [ ] Colour-coded based on action type (same as current)
- [ ] Existing alerts unaffected for non-followed wallets
- [ ] Copy suggestion amount respects category_filter

### 5. Paper Trading Engine

- [ ] Portfolio creation on first follow with auto_copy enabled
- [ ] Initial balance configurable (default $10,000)
- [ ] Trade execution on alert for followed wallets with auto_copy_enabled:
  - [ ] Category filter check (skip if filtered out)
  - [ ] Copy mode: proportional (X% of original size)
  - [ ] Copy mode: fixed ($X per trade)
  - [ ] Balance check (skip if insufficient funds)
  - [ ] Trade recorded in paper_trades
  - [ ] Position created/updated in paper_positions
- [ ] Position management:
  - [ ] Track avg_entry_price on multiple buys
  - [ ] Track unrealized_pnl using current market price
  - [ ] Track realized_pnl on full exit
- [ ] Exit detection:
  - [ ] When followed wallet exits a position, exit paper position
  - [ ] Manual close via API
  - [ ] Market resolution closes position automatically
- [ ] Portfolio metrics:
  - [ ] current_balance = initial + deposits - withdrawals + realized_pnl
  - [ ] total_pnl = realized_pnl + unrealized_pnl
  - [ ] roi = (total_pnl / initial_balance) * 100
- [ ] Error handling:
  - [ ] Insufficient balance → skip trade, log warning
  - [ ] Duplicate alert → skip (idempotent)
  - [ ] Zero price → skip (division by zero guard)

### 6. Portfolio API

- [ ] `GET /api/v1/portfolio` — overview (balance, total_pnl, roi, open_positions_count, total_trades)
- [ ] `GET /api/v1/portfolio/positions` — open positions with current value + unrealized_pnl
- [ ] `GET /api/v1/portfolio/trades` — trade history with pagination
- [ ] `POST /api/v1/portfolio/positions/{id}/close` — manually close a position
- [ ] `POST /api/v1/portfolio/reset` — reset portfolio (new initial_balance)
- [ ] Input validation (422 for invalid params)
- [ ] 404 for unknown position
- [ ] Pydantic schemas for all responses

### 7. ETL Pipeline

- [ ] `enrichment_follow_scoring` pipeline created in Mage AI
- [ ] Data loader `load_follow_metrics.py` — PG query: wallet_analytics + wallet_edge_snapshots + category_analytics
- [ ] Transformer `compute_follow_score.py` — implements follow scoring formula
- [ ] Data exporter `export_follow_scores.py` — UPDATE `wallet_analytics.follow_score`
- [ ] Pipeline registered in orchestration (after edge_scoring, before ranking)
- [ ] Extension to `smart_money_detection` — when exporting alerts, also generate paper trades if wallet is followed with auto_copy
- [ ] Existing pipelines still run correctly

### 8. Testing

- [ ] Unit tests for follow scoring formula (~8 tests)
- [ ] Unit tests for paper trading engine (~12 tests)
  - [ ] Proportional copy sizing
  - [ ] Fixed copy sizing
  - [ ] Category filter
  - [ ] Insufficient balance handling
  - [ ] Multiple buys tracking avg_entry_price
  - [ ] Position exit on followed wallet exit
  - [ ] Market resolution auto-close
  - [ ] Duplicate alert idempotency
  - [ ] Portfolio metrics calculation
  - [ ] Zero price guard
  - [ ] Portfolio reset
  - [ ] Empty portfolio edge cases
- [ ] API tests for follow endpoints (~8 tests)
  - [ ] List recommendations
  - [ ] Follow a wallet
  - [ ] List followed wallets
  - [ ] Update follow settings
  - [ ] Unfollow wallet
  - [ ] Follow unknown wallet (404)
  - [ ] Follow invalid params (422)
- [ ] API tests for portfolio endpoints (~7 tests)
  - [ ] Portfolio overview
  - [ ] List positions
  - [ ] Trade history
  - [ ] Manual close
  - [ ] Portfolio reset
  - [ ] Close unknown position (404)
  - [ ] Portfolio before any trades
- [ ] Integration tests (~12 tests)
  - [ ] wallet_follows table queryable
  - [ ] paper_portfolios table queryable
  - [ ] paper_positions table queryable
  - [ ] paper_trades table queryable
  - [ ] FK integrity for all new tables
  - [ ] NOT NULL constraints
  - [ ] follow_score column exists in wallet_analytics
  - [ ] follow_score in [0, 1]
  - [ ] ROW_THRESHOLDS updated
- [ ] All tests pass
- [ ] Migration forward + backward verified
- [ ] No regression on existing tests (~176 → ~215 total)

### 9. Documentation

- [ ] AGENTS.md updated with new pipeline(s)
- [ ] CHANGELOG.md updated (v0.4.0 → v0.5.0)
- [ ] README.md updated with new API endpoints
- [ ] Architecture diagram updated
- [ ] This sign-off checklist completed

### 10. Infrastructure

- [ ] Seed dump refreshed after pipeline run
- [ ] All CI jobs pass (lint, api-tests, integration-tests)
- [ ] MyPy strict — 0 errors

---

## Demo Materials

> **Captured on**: {date}

### Key Endpoint Responses

```json
{
  "follow_recommendations": [
    {"wallet": "0x123...", "follow_score": 0.92, "reason": "Top 1% edge score, Politics specialist, 340 trades"},
  ],
  "portfolio": {
    "balance": 10420.50,
    "total_pnl": 420.50,
    "roi": 4.2,
    "open_positions": 3
  }
}
```

### Test Results

```
215 passed in 12.3s
```

---

## Blocker Tracking

| Priority | Blocker | Resolved | Notes |
|---|---|---|---|
| 🟡 Medium | Real-time price feed for unrealized PnL | ⏳ TBD | Can use current outcome.price from outcomes table |
| 🟡 Medium | Paper trade execution on alert depends on alert pipeline timing | ⏳ TBD | May need a separate paper_trade_generator pipeline |
| 🟢 Low | Single-user mode limits testing | ❌ Won't fix | Multi-user auth deferred |

---

## Release Procedure

```bash
# 1. Run all migrations
alembic upgrade head

# 2. Run full test suite
python -m pytest app/tests/ -v

# 3. Lint and type-check
ruff check app/ && mypy app/ --strict

# 4. Run all pipelines incl. enrichment_follow_scoring
./scripts/run-all-pipelines.sh

# 5. Verify new data
psql -U app -d polymarket -c "SELECT COUNT(*) FROM wallet_follows;"
psql -U app -d polymarket -c "SELECT COUNT(*) FROM paper_portfolios;"
psql -U app -d polymarket -c "
    SELECT wallet, follow_score
    FROM wallet_analytics
    WHERE follow_score IS NOT NULL
    ORDER BY follow_score DESC
    LIMIT 10;
"

# 6. Test API endpoints
curl "http://localhost:8000/api/v1/follow/recommendations?limit=5"
curl "http://localhost:8000/api/v1/portfolio"

# 7. Refresh seed dump
./scripts/refresh-seed.sh
git add docker/initdb/seed.sql

# 8. Stage and commit
git add -A
git commit -m "feat: Phase 5 — Follow & Paper Trading"

# 9. Tag & push
git tag -a v0.5.0 -m "Phase 5 — Follow & Paper Trading"
git push origin v0.5.0

# 10. Mark Phase 5 progress in ROADMAP.md
```
