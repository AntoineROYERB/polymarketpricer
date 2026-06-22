# Phase 3 — Smart Money Detection — Sign-off Checklist

> **Objective**: Track completion of all Phase 3 deliverables before starting Phase 4.
> **Status**: ❌ Pending
> **Version**: v0.3.0

## Phase Description

**Smart Money Detection** — detects actionable trades by high-performing wallets and delivers alerts via Discord and WebSocket.

### What this phase delivers

- Migration `005_smart_money_alerts.py` — `alerts` and `alert_rules` tables
- `smart_money_detection` ETL pipeline — classify actions, apply rules, dedup by cooldown
- `GET /api/v1/alerts` endpoints — list, filter by wallet, stats
- `WS /api/v1/alerts/ws` — real-time WebSocket stream
- Discord delivery — `alert_service.py` with retry logic and embed formatting
- Background task `alert_delivery_loop()` in app lifespan
- 22 new tests (8 unit/API + 6 pure unit + 8 integration)

### What this phase does NOT cover

> - Email/SMS/Telegram notification channels (deferred)
> - Historical backfill of smart money alerts (deferred)

---

## Deliverables Overview

| # | Feature | Plan File | Est. Complexity |
|---|---|---|---|
| 1 | Database schema | `./01-database-schema.md` | Medium |
| 2 | Alert detection pipeline | `./02-alert-pipeline.md` | High |
| 3 | Discord delivery | `./03-discord-delivery.md` | Medium |
| 4 | API + WebSocket endpoints | `./04-api-endpoints.md` | Medium |
| 5 | Testing | `./05-testing.md` | Medium |

---

## Detailed Checklist

### 1. Database Schema

- [ ] Migration `005_smart_money_alerts.py` created
- [ ] `alerts` table: id, wallet, market_id, action, price, position_size, wallet_score, category, market_question, detected_at, notified_at, delivery_attempts
- [ ] `alert_rules` table: id, wallet (nullable, unique), min_score, min_position_size, min_liquidity, cooldown_minutes, discord_webhook_url, active
- [ ] Foreign keys: `alerts.wallet` → `wallets.wallet`, `alerts.market_id` → `markets.id`
- [ ] Indexes: detected_at DESC, wallet, category, unnotified, wallet+market
- [ ] Global default rule seeded (`wallet IS NULL`, min_score=80, min_position_size=500, min_liquidity=1000)
- [ ] SQLAlchemy models `Alert` and `AlertRule` in `app/db/models.py`
- [ ] Pydantic schemas `AlertAction`, `AlertItem`, `AlertListResponse` in `app/models/schemas.py`
- [ ] Downgrade works cleanly
- [ ] Existing Phase 1 + Phase 2 data intact after migration

### 2. Features / Business Logic

- [ ] Action classification: NEW_POSITION, POSITION_INCREASE, POSITION_DECREASE, FULL_EXIT
- [ ] Alert rule engine: wallet_score ≥ min_score, position_size ≥ min_position_size, liquidity ≥ min_liquidity
- [ ] Cooldown dedup: same wallet+market+action not re-triggered within N minutes
- [ ] Per-wallet rule override with global default fallback
- [ ] Max 3 delivery retries per alert

### 3. ETL Pipeline

- [ ] `smart_money_detection` pipeline created in Mage AI
- [ ] Data loader `load_recent_position_changes.py` — PG query for recent position_history
- [ ] Transformer `detect_smart_money_alerts.py` — classify, enrich, apply rules, dedup
- [ ] Data exporter `export_alerts.py` — INSERT into `alerts` with cooldown check
- [ ] Pipeline registered in orchestration (after `trigger_verify`)
- [ ] `trigger_smart_money.py` exporter created
- [ ] Pipeline completes within 30s SLA
- [ ] Existing 8 pipelines still run correctly

### 4. Discord Delivery + WebSocket

- [ ] `app/services/alert_service.py` — `poll_unnotified_alerts()`, `send_discord_alert()`, `mark_notified()`
- [ ] `app/services/ws_manager.py` — `ConnectionManager` with broadcast + heartbeat
- [ ] `DISCORD_WEBHOOK_URL` environment variable in config and docker-compose
- [ ] Discord embed formatting with action-based color coding
- [ ] Retry logic: 3 attempts, exponential backoff, max delivery_attempts
- [ ] Background task `alert_delivery_loop()` in `app/main.py` via lifespan
- [ ] Heartbeat every 30s, disconnect after 3 missed pongs

### 5. API Endpoints

- [ ] `GET /api/v1/alerts` — list alerts (paginated, filterable by category/min_score/wallet)
- [ ] `GET /api/v1/alerts/{wallet}` — alerts for specific wallet (404 if unknown)
- [ ] `GET /api/v1/alerts/stats` — aggregated counts
- [ ] `WS /api/v1/alerts/ws` — real-time WebSocket stream
- [ ] Input validation (422 for invalid params, 404 for unknown wallets)
- [ ] Pagination (limit/offset) on list endpoints
- [ ] All response models use Pydantic schemas

### 6. Testing

- [ ] 8 unit / API tests in `test_api/test_alerts.py`
- [ ] 6 pure unit tests in `test_action_classifier.py`
- [ ] 8 integration tests in `test_db_integrity.py`
- [ ] All 91 tests pass (69 existing + 22 new)
- [ ] Migration forward + backward verified
- [ ] No regression on existing tests

### 7. Documentation

- [ ] API reference updated in README.md (alerts endpoints, WebSocket)
- [ ] AGENTS.md updated with `smart_money_detection` pipeline + alert system
- [ ] CHANGELOG.md updated (v0.2.0 → v0.3.0)
- [ ] Architecture diagram updated (9 pipelines, Discord delivery, WebSocket)
- [ ] This sign-off checklist completed

### 8. Infrastructure

- [ ] Seed dump refreshed after pipeline run
- [ ] `DISCORD_WEBHOOK_URL` in CI secrets (if applicable)
- [ ] All CI jobs pass (lint, api-tests, integration-tests)
- [ ] MyPy strict — 0 errors

---

## Blocker Tracking

| Priority | Blocker | Resolved | Notes |
|---|---|---|---|
| 🔴 High | Discord webhook URL provisioning | ❌ | Requires creating a Discord webhook per environment |
| 🟡 Medium | WebSocket behind reverse proxy | ❌ | May need sticky sessions or broadcast via Redis |
| 🟡 Medium | position_history empty on fresh seed | ❌ | First alert cycle may produce no results; expected |
| 🟢 Low | Cooldown window tuned too short | ❌ | Default 15 min, adjust after monitoring |

---

## Release Procedure

```bash
# 1. Run all migrations
alembic upgrade head

# 2. Run full test suite
python -m pytest app/tests/ -v          # 91 passed

# 3. Run all pipelines incl. smart_money_detection
./scripts/run-all-pipelines.sh

# 4. Refresh seed dump
./scripts/refresh-seed.sh
git add docker/initdb/seed.sql

# 5. Commit documentation
git add CHANGELOG.md README.md AGENTS.md
git commit -m "docs: Phase 3 documentation for v0.3.0"

# 6. Tag & push
git tag -a v0.3.0 -m "Phase 3 — Smart Money Detection"
git push origin v0.3.0

# 7. Mark Phase 3 complete in ROADMAP.md
```
