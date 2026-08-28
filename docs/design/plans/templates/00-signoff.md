# Phase {N} — {Name} — Sign-off Checklist

> **Objective**: Track completion of all Phase {N} deliverables before starting Phase {N+1}.
> **Status**: ❌ Pending / 🚧 In progress / ✅ Complete
> **Version**: v0.{N}.0

## Phase Description

**{Name}** — {1-line summary of what the phase adds to the system}.

### Why this scope?

- **Narrow & self-contained** — schema, pipeline, API, and tests all align around a single feature set. No sprawling dependencies.
- **Reduces integration risk** — each phase ships independently, so downstream work depends on verified data and interfaces, not stubs.
- **Clear go/no-go** — the sign-off is a binary decision. If the checklist passes, the phase is done.
- **Audit trail** — every deliverable type (schema, pipeline, API, tests, docs, infra) has its own section. Mark non-applicable sections as **N/A** explicitly — skipping them hides scope gaps.

### What this phase delivers

> Non-exhaustive list — adapt to the phase.

- {Schema / migration changes}
- {ETL pipeline(s)}
- {API endpoint(s)}
- {Tests — mocked + integration}
- {Documentation & seed refresh}
- {... any other deliverable specific to this phase}

### What this phase does NOT cover

> Optional — uncomment if needed.
> - {Things deliberately deferred to a later phase}

---

## Deliverables Overview

| # | Feature | Plan File | Est. Complexity |
|---|---|---|---|
| 1 | {Feature 1} | `./0{n}-{feature}.md` | Low / Medium / High |
| 2 | {Feature 2} | ... | ... |

---

## Detailed Checklist

### 1. Database Schema

- [ ] New migration(s) created
- [ ] All new tables created with required columns
- [ ] Foreign keys to existing tables
- [ ] Indexes on common query patterns
- [ ] Downgrade works cleanly
- [ ] Existing data from previous phases intact

### 2. Features / Business Logic

- [ ] Core feature implemented
- [ ] Edge cases handled
- [ ] Performance within expected bounds

### 3. ETL Pipeline

- [ ] Pipeline created in Mage AI
- [ ] Data loaders implemented
- [ ] Transformer(s) implemented
- [ ] Data exporter(s) implemented
- [ ] Pipeline registered in orchestration
- [ ] Pipeline completes within SLA
- [ ] Existing pipelines still run correctly

### 4. API Endpoints

- [ ] All new endpoints implemented
- [ ] Input validation (404 for invalid params)
- [ ] Pagination where applicable
- [ ] Pydantic schemas in `app/models/schemas.py`

### 5. Testing

- [ ] Unit / API tests (mocked) — `test_api/`
- [ ] Integration tests (real DB) — `test_db_integrity.py`
- [ ] Classifier / pure unit tests where applicable
- [ ] All tests pass
- [ ] Migration forward + backward verified
- [ ] No regression on existing tests

### 6. Documentation

- [ ] API reference updated in README.md
- [ ] Architecture diagram updated
- [ ] AGENTS.md updated with new pipeline(s)
- [ ] CHANGELOG.md updated
- [ ] This sign-off checklist completed

### 7. Infrastructure

- [ ] Seed dump refreshed after pipeline run
- [ ] All CI jobs pass (lint, api-tests, integration-tests)
- [ ] MyPy strict — 0 errors

---

## Demo Materials

> **Captured on**: {date}

### Key Endpoint Responses

```json
{...}
```

### Test Results

```
{N} passed in {time}
```

### Database Volume

```
{N} tables, {N} total rows
```

---

## Blocker Tracking

| Priority | Blocker | Resolved | Notes |
|---|---|---|---|
| 🔴 High | ... | ❌ | ... |
| 🟡 Medium | ... | ❌ | ... |
| 🟢 Low | ... | ❌ | ... |

---

## Release Procedure

```bash
# 1. Run full test suite
python -m pytest app/tests/ -v

# 2. Run all pipelines
./scripts/run-all-pipelines.sh

# 3. Refresh seed dump
./scripts/refresh-seed.sh
git add docker/initdb/seed.sql

# 4. Commit documentation
git add CHANGELOG.md README.md AGENTS.md
git commit -m "docs: Phase {N} documentation for v0.{N}.0"

# 5. Tag & push
git tag -a v0.{N}.0 -m "Phase {N} — {Name}"
git push origin v0.{N}.0

# 6. Mark Phase {N} complete in ROADMAP.md
```
