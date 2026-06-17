# CI/CD Pipeline Setup

## Objective

Set up GitHub Actions to automatically run tests on every push and pull request, satisfying the Phase 1 deliverable *"Ensure CI passes"*.

---

## Current State

No `.github/workflows/` directory exists. Tests must be run manually.

---

## Pipeline Requirements

### Trigger on
- Push to `main`
- Pull requests targeting `main`
- Manual trigger (`workflow_dispatch`)

### Jobs

#### 1. Lint & Type Check
| Tool | Command |
|---|---|
| Ruff | `ruff check .` |
| MyPy | `mypy app/` (if configured) |

#### 2. Unit / API Tests
- Mock-based tests in `app/tests/test_api/`
- No database required
- Fast (< 30s)

#### 3. Integration Tests
- Requires PostgreSQL
- Tests in `app/tests/test_db_integrity.py`
- Must start a Postgres service container
- Uses `psycopg2` (synchronous)

---

## Proposed Workflow

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
          cache: pip
      - run: pip install -r requirements.txt
      - run: ruff check .

  api-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
          cache: pip
      - run: pip install -r requirements.txt
      - run: python -m pytest app/tests/test_api/ -v

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: app
          POSTGRES_PASSWORD: app
          POSTGRES_DB: polymarket
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
          cache: pip
      - run: pip install -r requirements.txt
      - run: python -m pytest app/tests/test_db_integrity.py -m integration -v
        env:
          DATABASE_URL: postgresql+asyncpg://app:app@localhost:5432/polymarket
```

---

## Considerations

### Seed Data for Integration Tests
Integration tests rely on database tables being populated. Options:

1. **Use the seed dump** — Restore `docker/initdb/seed.sql` into the Postgres service
2. **Run pipelines in CI** — Slow and requires Mage AI
3. **Use a lighter test fixture** — Create a minimal SQL dump just for tests

**Recommendation:** Option 1 — restore the seed dump in a `db-setup` step before running tests.

### Environment Variables
The app reads `DATABASE_URL` from the environment. The CI job must set this to point at the service container.

### Secrets Required
None for open source (app credentials are `app/app`).

---

## Deliverables

- [ ] Add `.github/workflows/ci.yml`
- [ ] Verify lint + API tests pass on push
- [ ] Verify integration tests pass with service container
- [ ] Add status badge to `README.md`

```markdown
![CI](https://github.com/<owner>/polymarketpricer/actions/workflows/ci.yml/badge.svg)
```
