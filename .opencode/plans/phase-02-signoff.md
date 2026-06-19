# Phase 2 — Sign-off Checklist

> **Objective**: Track completion of all Phase 2 deliverables before starting Phase 3.
> **Status**: Not started — planning complete.
> **Target version**: v0.2.0

---

## Deliverables Overview

| # | Feature | Plan File | Est. Complexity |
|---|---|---|---|
| 1 | Database schema | `phase-02-database-schema.md` | Medium |
| 2 | Category mapping | `phase-02-category-mapping.md` | High |
| 3 | ETL pipeline | `phase-02-etl-pipeline.md` | High |
| 4 | API endpoints | `phase-02-api-endpoints.md` | Medium |
| 5 | Testing | `phase-02-testing.md` | Medium |

---

## Detailed Checklist

### 1. Database Schema

- [ ] New migration `002_category_analytics.py`
- [ ] `category_analytics` table created with all columns
- [ ] `category_rankings` table created with all columns
- [ ] Foreign keys to `wallets.wallet`
- [ ] Indexes on common query patterns
- [ ] Downgrade works cleanly
- [ ] Existing Phase 1 data intact

### 2. Category Mapping

- [ ] Tier 1: Raw API category → target category mapping table
- [ ] Tier 2: Event category inheritance
- [ ] Tier 3: Keyword classifier for 8 categories
- [ ] `mapped_category` column added to `markets`
- [ ] Classifier integrated into `market_discovery` pipeline
- [ ] ≥ 95% of markets classified
- [ ] Classifier tested with known input/output examples

### 3. ETL Pipeline

- [ ] `category_analytics` pipeline created in Mage AI
- [ ] `load_market_categories` data loader
- [ ] `compute_category_metrics` transformer (reuses Phase 1 helpers)
- [ ] `export_category_analytics` data exporter
- [ ] Category ranking (top 50 per category + specialists)
- [ ] Pipeline registered in `magic/scripts/run_all.py`
- [ ] Pipeline completes within 120s SLA
- [ ] Existing 6 pipelines still run correctly

### 4. API Endpoints

- [ ] `GET /api/v1/leaderboard/{category}`
- [ ] `GET /api/v1/leaderboard/{category}/specialists`
- [ ] `GET /api/v1/wallets/{address}/categories`
- [ ] `GET /api/v1/wallets/{address}/categories/{category}`
- [ ] Wallet profile includes `categories` field
- [ ] Valid category validation (404 for invalid)
- [ ] Pagination (limit/offset) on list endpoints
- [ ] Pydantic schemas in `app/models/schemas.py`

### 5. Testing

- [ ] 8 new API endpoint tests (mocked)
- [ ] 8 new integration tests (real DB)
- [ ] 10+ classifier unit tests
- [ ] All 67 tests pass (41 existing + 26 new)
- [ ] Migration forward + backward verified
- [ ] No regression on existing tests

### 6. Documentation

- [ ] API reference updated in README.md
- [ ] Architecture diagram updated
- [ ] AGENTS.md updated with new pipeline
- [ ] Demo materials captured

### 7. Infrastructure

- [ ] Seed dump refreshed after pipeline run
- [ ] All CI jobs pass (lint, api-tests, integration-tests)
- [ ] MyPy strict — 0 errors

---

## Blocker Tracking

| Priority | Blocker | Resolved | Notes |
|---|---|---|---|
| 🔴 High | Category quality for 95% NULL markets | ❌ | Keyword classifier needs validation |
| 🟡 Medium | Pipeline SLA for 8× category groups | ❌ | May need optimization |
| 🟢 Low | Migration order with existing seed | ❌ | Must preserve seed data |

---

## Release Procedure

```bash
# 1. Run full test suite
python -m pytest app/tests/ -v          # 67 passed

# 2. Run all pipelines
./scripts/run-all-pipelines.sh

# 3. Refresh seed dump
./scripts/refresh-seed.sh

# 4. Tag & push
git tag -a v0.2.0 -m "Phase 2 — Niche Expertise Detection"
git push origin v0.2.0

# 5. Mark Phase 2 complete in ROADMAP.md
```
