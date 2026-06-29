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

- 5 new database tables (`wallet_follows`, `wallet_category_follow_scores`, `paper_portfolios`, `paper_positions`, `paper_trades`) + `follow_score` + `category_follow_scores` (JSONB) on `wallet_analytics`
- Follow recommendation scoring — **global** (edge + consistency + category expertise + recency + frequency) + **per-category** (edge + ROI percentile + win rate + specialist bonus + volume percentile + category recency)
- Wallet follow CRUD API + recommendations endpoint + **per-category recommendations**
- Enhanced Discord alerts with wallet follow status, **top category scores**, and copy-trade suggestions
- Paper trading engine — auto-copy trades from followed wallets with configurable sizing (proportional or fixed), category filtering
- Portfolio API — overview, positions, trade history, manual close, portfolio reset
- ETL pipeline `enrichment_follow_scoring` (global + per-category scoring) + extension to `smart_money_detection` for paper trade generation
- ~61 new tests (unit + API + integration)

### What this phase does NOT cover

> - Real-money trading integration — deferred; Phase 5 is simulation-only
> - Multi-user authentication — deferred; single-user mode with `user_id` placeholder
> - Dashboard UI — deferred to Phase 6
> - Historical backfill of paper trades — deferred; paper portfolio starts empty on creation

---

## Deliverables Overview

| # | Feature | Plan File | Est. Complexity |
|---|---|---|---|---|
| 1 | Database schema | `./01-database-schema.md` | Medium (4 migrations → 5 migrations) |
| 2 | Follow recommendation scoring | `./02-follow-scoring.md` | Medium (added per-category formula) |
| 3 | Wallet follow API | `./03-follow-api.md` | Medium (added 2 per-category endpoints) |
| 4 | Enhanced Discord alerts | `./04-enhanced-alerts.md` | Low (added category scores to embed) |
| 5 | Paper trading engine | `./05-paper-trading-engine.md` | High |
| 6 | Portfolio API | `./06-portfolio-api.md` | Medium |
| 7 | ETL pipeline | `./07-etl-pipeline.md` | High (added per-category transformer + exporter) |
| 8 | Testing | `./08-testing.md` | Medium (47 → 61 tests) |

---

## Detailed Checklist

### 1. Database Schema

- [ ] Migration `018_add_wallet_follows.py` — `wallet_follows` table
- [ ] Migration `019_add_paper_trading.py` — `paper_portfolios`, `paper_positions`, `paper_trades` tables
- [ ] Migration `020_add_follow_score.py` — `follow_score` column on `wallet_analytics`
- [ ] Migration `021_add_category_follow_scores.py` — `wallet_category_follow_scores` table + `category_follow_scores` JSONB on `wallet_analytics`
- [ ] Foreign keys to `wallets.wallet`, `markets.id`, `alerts.id`, `categories.category` (where applicable)
- [ ] Indexes on common query patterns (wallet, portfolio_id, status, detected_at, category follow score)
- [ ] Composite PKs where appropriate
- [ ] SQLAlchemy models for all 5 new tables (incl. `WalletCategoryFollowScore`)
- [ ] Pydantic schemas for all new models (incl. per-category follow score schemas)
- [ ] Downgrade works cleanly
- [ ] Existing Phase 1–4 data intact after migration

### 2. Follow Recommendation Scoring

#### Global scoring

- [ ] Formula implemented: `0.30*edge_score + 0.20*consistency + 0.20*category_specialization + 0.15*recency_decay + 0.15*trade_frequency`
- [ ] Category specialization score computed from category_analytics (is_specialist flag, category_rank)
- [ ] Recency decay based on days since last trade (exponential decay)
- [ ] Trade frequency score based on trades per month
- [ ] Missing data defaults to 0 (no crash)
- [ ] Normalised to [0, 1] range (no min-max needed)
- [ ] Global follow recommendations endpoint returns top-N wallets by follow_score

#### Per-category scoring (NEW)

- [ ] Formula implemented: `0.25*edge_score + 0.25*category_roi_percentile + 0.20*category_win_rate + 0.15*specialist_bonus + 0.10*category_volume_percentile + 0.05*category_recency`
- [ ] ROI percentile computed per category across all wallets (window function)
- [ ] Volume percentile computed per category across all wallets
- [ ] Specialist bonus: 1.0 if is_specialist, 0.5 otherwise
- [ ] Category recency: exponential decay based on days since last trade in that category
- [ ] Recommendation thresholds: >= 0.70 → FOLLOW, >= 0.35 → WATCH, < 0.35 → IGNORE
- [ ] Reason generation: top 2-3 reasons based on dominant signals
- [ ] Stored in `wallet_category_follow_scores` table and as JSONB in `wallet_analytics.category_follow_scores`
- [ ] Category follow leaderboard endpoint returns top-N wallets by category

### 3. Wallet Follow API

#### Follow CRUD

- [ ] `GET /api/v1/follow/recommendations` — recommended wallets (global follow_score)
- [ ] `GET /api/v1/follow` — list followed wallets with config
- [ ] `POST /api/v1/follow/{wallet}` — follow with body (label, auto_copy, copy_mode, copy_value, category_filter)
- [ ] `PATCH /api/v1/follow/{wallet}` — update follow settings
- [ ] `DELETE /api/v1/follow/{wallet}` — unfollow (soft delete)
- [ ] Input validation (422 for invalid params)
- [ ] Pagination where applicable
- [ ] 404 for unknown wallet
- [ ] Pydantic schemas for all request/response models

#### Per-category recommendations (NEW)

- [ ] `GET /api/v1/follow/recommendations/by-category/{category}` — top wallets to follow in a specific category
- [ ] `GET /api/v1/follow/recommendations/{wallet}/by-category` — all per-category follow scores for a wallet
- [ ] 404 for invalid category
- [ ] 404 for unknown wallet
- [ ] Pydantic schemas: `CategoryFollowLeaderboardEntry`, `CategoryFollowLeaderboardResponse`, `CategoryFollowScoreItem`, `WalletCategoryFollowScoresResponse`

### 4. Enhanced Discord Alerts

- [ ] Detect if alert wallet is followed by user
- [ ] Add "You follow this trader" indicator in embed
- [ ] Add top category scores in embed: "🏆 Politics (FOLLOW, 0.92) | Crypto (WATCH, 0.45)"
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

#### Global follow scoring

- [ ] `enrichment_follow_scoring` pipeline created in Mage AI
- [ ] Data loader `load_follow_metrics.py` — PG query: wallet_analytics + wallet_edge_snapshots + category_analytics + trades
- [ ] Transformer `compute_follow_score.py` — implements global follow scoring formula
- [ ] Data exporter `export_follow_scores.py` — UPDATE `wallet_analytics.follow_score`
- [ ] Pipeline registered in orchestration (after edge_scoring, before ranking)

#### Per-category follow scoring (NEW)

- [ ] Extended data loader query: loads per-wallet × per-category metrics from `category_analytics`, `trades`, `markets`
- [ ] Transformer `compute_category_follow_scores.py` — implements per-category follow scoring formula
- [ ] Data exporter `export_category_follow_scores.py` — UPSERT to `wallet_category_follow_scores` + UPDATE `wallet_analytics.category_follow_scores`
- [ ] Pipeline metadata.yaml updated with per-category block

#### Paper trading

- [ ] Extension to `smart_money_detection` — when exporting alerts, also generate paper trades if wallet is followed with auto_copy
- [ ] Existing pipelines still run correctly

### 8. Testing

- [ ] Unit tests for global follow scoring formula (~8 tests)
- [ ] Unit tests for per-category follow scoring formula (~4 tests)
  - [ ] Perfect category score → 1.0
  - [ ] Zero category score → minimal score
  - [ ] Recommendation thresholds (FOLLOW / WATCH / IGNORE)
  - [ ] Reason generation from dominant signals
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
- [ ] API tests for follow endpoints (~11 tests)
  - [ ] List recommendations (global)
  - [ ] Recommendations by category
  - [ ] Recommendations by invalid category (404)
  - [ ] Wallet per-category recommendations
  - [ ] Follow a wallet
  - [ ] List followed wallets
  - [ ] Update follow settings
  - [ ] Unfollow wallet
  - [ ] Follow unknown wallet (404)
  - [ ] Follow invalid params (422)
  - [ ] Follow duplicate (409)
- [ ] API tests for portfolio endpoints (~7 tests)
  - [ ] Portfolio overview
  - [ ] List positions
  - [ ] Trade history
  - [ ] Manual close
  - [ ] Portfolio reset
  - [ ] Close unknown position (404)
  - [ ] Portfolio before any trades
- [ ] Integration tests (~19 tests)
  - [ ] wallet_follows table queryable + FK + NOT NULL
  - [ ] paper_portfolios table queryable
  - [ ] paper_positions table queryable + FK + NOT NULL + status valid
  - [ ] paper_trades table queryable
  - [ ] wallet_category_follow_scores table queryable
  - [ ] wallet_category_follow_scores FK to wallets
  - [ ] wallet_category_follow_scores FK to categories
  - [ ] wallet_category_follow_scores NOT NULL constraints
  - [ ] wallet_category_follow_scores follow_score in [0, 1]
  - [ ] wallet_category_follow_scores valid recommendation values
  - [ ] wallet_category_follow_scores is_specialist boolean
  - [ ] follow_score column exists in wallet_analytics
  - [ ] category_follow_scores column exists in wallet_analytics
  - [ ] follow_score in [0, 1]
  - [ ] Portfolio balance non-negative
  - [ ] ROW_THRESHOLDS updated
- [ ] All tests pass
- [ ] Migration forward + backward verified
- [ ] No regression on existing tests (~176 → ~237 total)

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
  "recommendations_by_category": [
    {"wallet": "0xabc...", "follow_score": 0.92, "recommendation": "FOLLOW", "category": "politics", "reasons": ["Top 3% ROI", "Politics specialist"]}
  ],
  "wallet_category_scores": {
    "wallet": "0x123...",
    "global_follow_score": 0.85,
    "category_scores": [
      {"category": "politics", "follow_score": 0.92, "recommendation": "FOLLOW"},
      {"category": "crypto", "follow_score": 0.45, "recommendation": "WATCH"},
      {"category": "sports", "follow_score": 0.12, "recommendation": "IGNORE"}
    ]
  },
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
237 passed in 14.1s
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
psql -U app -d polymarket -c "SELECT COUNT(*) FROM wallet_category_follow_scores;"
psql -U app -d polymarket -c "SELECT COUNT(*) FROM paper_portfolios;"
psql -U app -d polymarket -c "
    SELECT wallet, follow_score
    FROM wallet_analytics
    WHERE follow_score IS NOT NULL
    ORDER BY follow_score DESC
    LIMIT 10;
"
psql -U app -d polymarket -c "
    SELECT wallet, category, follow_score, recommendation
    FROM wallet_category_follow_scores
    WHERE snapshot_date = CURRENT_DATE
      AND recommendation = 'FOLLOW'
    ORDER BY follow_score DESC
    LIMIT 10;
"

# 6. Test API endpoints
curl "http://localhost:8000/api/v1/follow/recommendations?limit=5"
curl "http://localhost:8000/api/v1/follow/recommendations/by-category/politics?limit=5"
curl "http://localhost:8000/api/v1/follow/recommendations/0x.../by-category"
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
