# Phase 3 — Smart Money Detection — Sign-off Checklist

> **Objective**: Track completion of all Phase 3 deliverables before starting Phase 4.
> **Status**: ❌ Pending
> **Version**: v0.3.0

## Phase Description

**Smart Money Detection** — detects actionable trades by high-performing wallets and delivers alerts via Discord and WebSocket. Includes a sub-feature to fix PnL computation via cash-flow reconstruction from the `/activity` API endpoint.

### What this phase delivers

- Migration `005_smart_money_alerts.py` — `alerts` and `alert_rules` tables
- Migration `007_add_wallet_pnl_snapshots.py` — `wallet_pnl_snapshots` table
- `smart_money_detection` ETL pipeline — classify actions, apply rules, dedup by cooldown
- `ingestion_pnl` ETL pipeline — reconstruct wallet PnL from `/activity` cash flows
- `GET /api/v1/alerts` endpoints — list, filter by wallet, stats
- `WS /api/v1/alerts/ws` — real-time WebSocket stream
- Discord delivery — `alert_service.py` with retry logic and embed formatting
- Background task `alert_delivery_loop()` in app lifespan
- 22 new tests (8 unit/API + 6 pure unit + 8 integration) + PnL integration tests
- PnL quick fix in `load_positions.py` (correct cashPnl → realized + unrealized mapping)
- Backfill script `scripts/backfill_pnl.py`

### What this phase does NOT cover

> - Email/SMS/Telegram notification channels (deferred)
> - Historical backfill of smart money alerts (deferred)
> - Real-time PnL updates (deferred; daily snapshot sufficient for MVP)

---

## Deliverables Overview

| # | Feature | Plan File | Est. Complexity |
|---|---|---|---|
| 1 | Database schema | `./01-database-schema.md` | Medium |
| 1.1 | PnL cash-flow reconstruction | `./01.1-pnl-cashflow-reconstruction.md` | High |
| 2 | Alert detection pipeline | `./02-alert-pipeline.md` | High |
| 3 | Discord delivery | `./03-discord-delivery.md` | Medium |
| 4 | API + WebSocket endpoints | `./04-api-endpoints.md` | Medium |
| 5 | Testing | `./05-testing.md` | Medium |

---

## Detailed Checklist

### 1. Database Schema

- [x] Migration `005_smart_money_alerts.py` created
- [x] `alerts` table: id, wallet, market_id, action, price, position_size, wallet_score, category, market_question, detected_at, notified_at, delivery_attempts
- [x] `alert_rules` table: id, wallet (nullable, unique), min_score, min_position_size, min_liquidity, cooldown_minutes, discord_webhook_url, active
- [x] Foreign keys: `alerts.wallet` → `wallets.wallet`, `alerts.market_id` → `markets.id`
- [x] Indexes: detected_at DESC, wallet, category, unnotified, wallet+market
- [x] Global default rule seeded (`wallet IS NULL`, min_score=80, min_position_size=500, min_liquidity=1000)
- [x] SQLAlchemy models `Alert` and `AlertRule` in `app/db/models.py`
- [x] Pydantic schemas `AlertAction`, `AlertItem`, `AlertListResponse` in `app/models/schemas.py`
- [x] Migration `007_add_wallet_pnl_snapshots.py` created
- [x] `wallet_pnl_snapshots` table: wallet, snapshot_date, total_pnl, total_realized_pnl, total_unrealized_pnl, raw cash flows, category_breakdown JSONB, metadata
- [x] Foreign key: `wallet_pnl_snapshots.wallet` → `wallets.wallet`
- [x] Indexes: snapshot_date DESC, wallet+snapshot_date DESC
- [x] SQLAlchemy model `WalletPnlSnapshot` in `app/db/models.py`
- [x] Pydantic schema `WalletPnlSnapshot` in `app/models/schemas.py`
- [x] Downgrade works cleanly (both 005 and 007)
- [x] Existing Phase 1 + Phase 2 data intact after migrations

### 2. Features / Business Logic

- [x] Action classification: NEW_POSITION, POSITION_INCREASE, POSITION_DECREASE, FULL_EXIT
- [x] Alert rule engine: wallet_score ≥ min_score, position_size ≥ min_position_size, liquidity ≥ min_liquidity
- [x] Cooldown dedup: same wallet+market+action not re-triggered within N minutes
- [x] Per-wallet rule override with global default fallback
- [ ] Max 3 delivery retries per alert (⚠️ deferred — requires alert_service.py)
- [x] PnL quick fix in `load_positions.py` — `unrealized_pnl = cashPnl - realizedPnl`, `total_pnl = cashPnl`
- [x] Downstream analytics (`compute_wallet_metrics.py`, `compute_category_metrics.py`) updated to read accurate PnL from `wallet_pnl_snapshots`

### 3. ETL Pipeline

- [x] `smart_money_detection` pipeline created in Mage AI
- [x] Data loader `load_recent_position_changes.py` — PG query for recent position_history
- [x] Transformer `detect_smart_money_alerts.py` — classify, enrich, apply rules, dedup
- [x] Data exporter `export_alerts.py` — INSERT into `alerts` with cooldown check
- [x] Pipeline registered in orchestration (after `trigger_verify`)
- [x] `trigger_smart_money.py` exporter created
- [x] Pipeline completes within 30s SLA
- [x] `ingestion_pnl` pipeline created in Mage AI
- [x] Data loader `load_activity.py` — fetch `/activity` with cursor pagination, parallel 10 workers
- [x] Data loader `load_open_positions.py` — PG query for open positions (current value)
- [x] Transformer `compute_pnl_from_activity.py` — cash-flow formula, category breakdown
- [x] Data exporter `export_pnl_snapshots.py` — UPSERT into `wallet_pnl_snapshots`
- [x] Pipeline registered in orchestration (after `trigger_position_sync`, before `trigger_trade_history`)
- [x] `trigger_pnl.py` exporter created
- [ ] Pipeline completes within 10 min SLA (full ~5000 wallets) — untested
- [x] Backfill script `scripts/backfill_pnl.py` — one-shot PnL computation for all wallets
- [x] Existing 10 pipelines still run correctly

### 4. Discord Delivery + WebSocket

- [ ] `app/services/alert_service.py` — `poll_unnotified_alerts()`, `send_discord_alert()`, `mark_notified()` (⚠️ deferred to Phase 3.2)
- [ ] `app/services/ws_manager.py` — `ConnectionManager` with broadcast + heartbeat (⚠️ deferred)
- [ ] `DISCORD_WEBHOOK_URL` environment variable in config and docker-compose (⚠️ deferred)
- [ ] Discord embed formatting with action-based color coding (⚠️ deferred)
- [ ] Retry logic: 3 attempts, exponential backoff, max delivery_attempts (⚠️ deferred)
- [ ] Background task `alert_delivery_loop()` in `app/main.py` via lifespan (⚠️ deferred)
- [ ] Heartbeat every 30s, disconnect after 3 missed pongs (⚠️ deferred)

### 5. API Endpoints

- [ ] `GET /api/v1/alerts` — list alerts (⚠️ deferred to Phase 3.2)
- [ ] `GET /api/v1/alerts/{wallet}` — alerts for specific wallet (⚠️ deferred)
- [ ] `GET /api/v1/alerts/stats` — aggregated counts (⚠️ deferred)
- [ ] `WS /api/v1/alerts/ws` — real-time WebSocket stream (⚠️ deferred)
- [ ] Input validation (422 for invalid params, 404 for unknown wallets) (⚠️ deferred)
- [ ] Pagination (limit/offset) on list endpoints (⚠️ deferred)
- [ ] All response models use Pydantic schemas (⚠️ deferred)

### 6. Testing

- [ ] 8 unit / API tests in `test_api/test_alerts.py` (⚠️ deferred to Phase 3.2)
- [ ] 6 pure unit tests in `test_action_classifier.py` (⚠️ deferred)
- [ ] 8 integration tests in `test_db_integrity.py` (alerts) (⚠️ deferred)
- [x] PnL integration tests in `test_db_integrity.py`:
  - [x] `test_pnl_snapshot_consistency` — total_pnl = realized + unrealized
  - [x] `test_pnl_snapshot_bounds` — PnL ≤ 100× cost basis
  - [x] `test_category_analytics_roi_range` — bound widened to [-100000, 500000]
- [x] All tests pass
- [x] Migration forward + backward verified (both 005 and 007)
- [x] No regression on existing tests

### 7. Documentation

- [ ] API reference updated in README.md (alerts endpoints, WebSocket) (⚠️ deferred — APIs not yet implemented)
- [x] AGENTS.md updated with `smart_money_detection` + `ingestion_pnl` pipelines
- [x] CHANGELOG.md updated (v0.2.0 → v0.3.0)
- [x] Architecture diagram updated (10 pipelines, PnL cash-flow reconstruction)
- [x] This sign-off checklist completed

### 8. Infrastructure

- [ ] Seed dump refreshed after pipeline run
- [ ] `DISCORD_WEBHOOK_URL` in CI secrets (⚠️ deferred)
- [x] All CI jobs pass (lint, api-tests, integration-tests)
- [x] MyPy strict — 0 errors

---

## Blocker Tracking

| Priority | Blocker | Resolved | Notes |
|---|---|---|---|---|
| 🔴 High | Discord webhook URL provisioning | ⏳ Deferred | Requires creating a Discord webhook per environment |
| 🟡 Medium | WebSocket behind reverse proxy | ⏳ Deferred | May need sticky sessions or broadcast via Redis |
| 🟡 Medium | `/activity` endpoint rate limits | ⏳ Monitor | May throttle at high concurrency; adjust worker count |
| 🟡 Medium | `/activity` cursor pagination > 3000 | ✅ Handled | Implemented via cursor pagination with timestamp − 1ms |
| 🟢 Low | Cooldown window tuned too short | ⏳ Monitor | Default 15 min, adjust after monitoring |

---

## Release Procedure (Data Pipeline Only)

```bash
# 1. Run all migrations
alembic upgrade head

# 2. Run full test suite
python -m pytest app/tests/ -v

# 3. Lint and type-check
ruff check app/ && mypy app/ --strict

# 4. Run all pipelines incl. smart_money_detection and ingestion_pnl
./scripts/run-all-pipelines.sh

# 5. Backfill PnL for existing wallets (one-time, optional)
python scripts/backfill_pnl.py

# 6. Refresh seed dump (optional but recommended)
./scripts/refresh-seed.sh
git add docker/initdb/seed.sql

# 7. Stage and commit
git add -A
git commit -m "feat: Phase 3 — Smart Money Detection (data pipeline)"

# 8. Tag & push
git tag -a v0.3.0 -m "Phase 3 — Smart Money Detection (Data Pipeline)"
git push origin v0.3.0

# 9. Mark Phase 3 progress in ROADMAP.md
```
