# Phase 5 — Follow & Paper Trading — Testing

> **Goal**: Verify follow scoring, paper trading engine, API endpoints, and database integrity for all new tables.
> **AI Agent Instructions**: Add unit, API, and integration tests for all Phase 5 features.

---

## 1. Unit Tests — Follow Scoring

New test file: `app/tests/test_follow_scoring.py`

### Scenarios (~8 tests)

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | `test_perfect_wallet_score` | Perfect edge (1.0), perfect consistency (1.0), 8 specialist categories, trade today, 50 trades/month | follow_score = 1.0 |
| 2 | `test_zero_edge_wallet` | edge_score=0, consistency=0.5, no specialists, 90 days since last trade, 10 trades/month | follow_score = ~0.20*0.5 + ... |
| 3 | `test_category_specialization_max` | 8 specialist categories, rank=1 | spec_score = 0.5*1 + 0.5*(1-0.01) = 0.995 |
| 4 | `test_category_specialization_none` | 0 specialists, no rows in category_analytics | spec_score = 0 (falls back to 0) |
| 5 | `test_recency_score_today` | days_since=0 | recency = e^0 = 1.0 |
| 6 | `test_recency_score_old` | days_since=365 | recency = e^(-365/90) ≈ 0.017 |
| 7 | `test_frequency_score_low` | 2 trades, 12 months active | tpm ≈ 0.17, score = 1/(1+e^(-0.1*(0.17-10))) ≈ 0.27 |
| 8 | `test_frequency_score_high` | 500 trades, 10 months active | tpm = 50, score ≈ 0.98 |

### Pure function tests (no DB needed)

```python
# app/tests/test_follow_scoring.py

import pytest
import math
from decimal import Decimal


@pytest.mark.parametrize("specialist_count,avg_rank,expected_min", [
    (8, 1, 0.99),
    (4, 25, 0.5 * 4/8 + 0.5 * (1 - 25/100)),
    (0, 50, 0.5 * 0 + 0.5 * (1 - 50/100)),
])
def test_category_specialization(specialist_count, avg_rank, expected_min):
    from app.services.follow_scoring import compute_category_specialization
    # ... test implementation


@pytest.mark.parametrize("days_since,expected", [
    (0, 1.0),
    (90, round(math.exp(-1), 6)),
    (365, round(math.exp(-365/90), 6)),
])
def test_recency_score(days_since, expected):
    from app.services.follow_scoring import compute_recency_score
    assert abs(compute_recency_score(days_since) - expected) < 0.01
```

---

## 2. Unit Tests — Paper Trading Engine

New test file: `app/tests/test_paper_trading.py`

### Scenarios (~12 tests)

| # | Test | Description |
|---|------|-------------|
| 1 | `test_proportional_copy` | 5% of $12,000 = $600 |
| 2 | `test_fixed_copy` | Fixed $100 per trade |
| 3 | `test_category_filter_include` | alert.category in filter → execute |
| 4 | `test_category_filter_exclude` | alert.category not in filter → skip |
| 5 | `test_insufficient_balance` | copy amount > balance → adjust to balance |
| 6 | `test_insufficient_balance_zero` | balance = 0 → skip |
| 7 | `test_multiple_buys_weighted_avg` | 2 buys at different prices → correct avg |
| 8 | `test_full_exit` | Sell all shares → calculate realized PnL, position closed |
| 9 | `test_partial_exit` | Sell half shares → shares reduced, partial PnL |
| 10 | `test_market_resolution_win` | Market resolves → auto-close at 1.0 |
| 11 | `test_market_resolution_loss` | Market resolves → auto-close at 0.0 |
| 12 | `test_duplicate_alert_idempotent` | Same alert processed twice → second skipped |

---

## 3. API Tests — Follow Endpoints

New test file: `app/tests/test_api/test_follow_endpoints.py`

### Scenarios (~8 tests)

| # | Test | Method | Expected |
|---|------|--------|----------|
| 1 | `test_recommendations_empty` | GET `/api/v1/follow/recommendations` | 200, empty data |
| 2 | `test_recommendations_with_data` | GET `/api/v1/follow/recommendations` | 200, list of wallets |
| 3 | `test_follow_wallet` | POST `/api/v1/follow/{wallet}` | 201, FollowResponse |
| 4 | `test_follow_unknown_wallet` | POST `/api/v1/follow/0xdeadbeef` | 404 |
| 5 | `test_follow_duplicate` | POST `/api/v1/follow/{wallet}` twice | 409 |
| 6 | `test_list_follows` | GET `/api/v1/follow` | 200, list |
| 7 | `test_update_follow` | PATCH `/api/v1/follow/{wallet}` | 200, updated |
| 8 | `test_unfollow` | DELETE `/api/v1/follow/{wallet}` | 204 |

---

## 4. API Tests — Portfolio Endpoints

New test file: `app/tests/test_api/test_portfolio_endpoints.py`

### Scenarios (~7 tests)

| # | Test | Method | Expected |
|---|------|--------|----------|
| 1 | `test_portfolio_empty` | GET `/api/v1/portfolio` | 200, zero data |
| 2 | `test_portfolio_with_trades` | GET `/api/v1/portfolio` | 200, with PnL |
| 3 | `test_list_positions` | GET `/api/v1/portfolio/positions` | 200, list |
| 4 | `test_list_trades` | GET `/api/v1/portfolio/trades` | 200, paginated |
| 5 | `test_close_position` | POST `/api/v1/portfolio/positions/{id}/close` | 200, closed |
| 6 | `test_close_invalid_position` | POST `/api/v1/portfolio/positions/{bad-id}/close` | 404 |
| 7 | `test_reset_portfolio` | POST `/api/v1/portfolio/reset` | 200, reset |

---

## 5. Integration Tests

Add to `app/tests/test_db_integrity.py`:

### New row count thresholds

Add to `ROW_THRESHOLDS`:
```python
ROW_THRESHOLDS = {
    # ... existing ...
    "wallet_follows": 1,  # at least 1 follow (from seed or test data)
}
```

Note: `paper_portfolios`, `paper_positions`, `paper_trades` are user-created on demand, so they may have 0 rows unless a follow with auto_copy is configured.

### New integration tests (~12 tests)

```python
# ── Phase 5: Follow & Paper Trading ──────────────────────────────────

class TestPhase05Follow:
    """Integration tests for Phase 5 wallet_follows table."""

    def test_wallet_follows_queryable(self, db):
        """wallet_follows table exists and is queryable."""
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM wallet_follows")
        count = cur.fetchone()[0]
        assert count >= 0  # table exists

    def test_wallet_follows_fk_wallet(self, db):
        """wallet_follows.wallet FK references wallets.wallet."""
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM wallet_follows wf
            LEFT JOIN wallets w ON w.wallet = wf.wallet
            WHERE w.wallet IS NULL
        """)
        orphans = cur.fetchone()[0]
        assert orphans == 0, f"Found {orphans} orphan wallet_follows rows"

    def test_wallet_follows_not_null(self, db):
        """Critical columns have no NULLs."""
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM wallet_follows
            WHERE wallet IS NULL OR user_id IS NULL
               OR follow_value IS NULL
        """)
        nulls = cur.fetchone()[0]
        assert nulls == 0

    def test_wallet_follows_active_valid(self, db):
        """active column is boolean (0 or 1)."""
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM wallet_follows
            WHERE active NOT IN (true, false)
        """)
        invalid = cur.fetchone()[0]
        assert invalid == 0


class TestPhase05PaperTrading:
    """Integration tests for Phase 5 paper_trading tables."""

    def test_paper_portfolios_queryable(self, db):
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM paper_portfolios")
        count = cur.fetchone()[0]
        assert count >= 0

    def test_paper_positions_queryable(self, db):
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM paper_positions")
        count = cur.fetchone()[0]
        assert count >= 0

    def test_paper_trades_queryable(self, db):
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM paper_trades")
        count = cur.fetchone()[0]
        assert count >= 0

    def test_paper_portfolios_fk(self, db):
        """paper_positions.portfolio_id FK -> paper_portfolios.id."""
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM paper_positions pp
            LEFT JOIN paper_portfolios pf ON pf.id = pp.portfolio_id
            WHERE pf.id IS NULL
        """)
        orphans = cur.fetchone()[0]
        assert orphans == 0

    def test_paper_positions_not_null(self, db):
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM paper_positions
            WHERE portfolio_id IS NULL OR market_id IS NULL
               OR shares IS NULL OR avg_entry_price IS NULL
        """)
        nulls = cur.fetchone()[0]
        assert nulls == 0

    def test_paper_positions_status_valid(self, db):
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM paper_positions
            WHERE status NOT IN ('OPEN', 'CLOSED', 'RESOLVED')
        """)
        invalid = cur.fetchone()[0]
        assert invalid == 0

    def test_paper_positions_balance_non_negative(self, db):
        """Portfolio current_balance must be >= 0."""
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM paper_portfolios
            WHERE current_balance < 0
        """)
        negative = cur.fetchone()[0]
        assert negative == 0


class TestPhase05FollowScore:
    """Integration tests for follow_score on wallet_analytics."""

    def test_follow_score_column_exists(self, db):
        cur = db.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'wallet_analytics'
              AND column_name = 'follow_score'
        """)
        assert cur.fetchone() is not None

    def test_follow_score_range(self, db):
        cur = db.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM wallet_analytics
            WHERE follow_score IS NOT NULL
              AND (follow_score < 0 OR follow_score > 1)
        """)
        out_of_range = cur.fetchone()[0]
        assert out_of_range == 0, f"Found {out_of_range} out-of-range follow_scores"
```

---

## Test Count Summary

| Test Suite | File | Existing | New | Total |
|------------|------|----------|-----|-------|
| Follow scoring unit | `test_follow_scoring.py` | 0 | 8 | 8 |
| Paper trading unit | `test_paper_trading.py` | 0 | 12 | 12 |
| Follow API | `test_api/test_follow_endpoints.py` | 0 | 8 | 8 |
| Portfolio API | `test_api/test_portfolio_endpoints.py` | 0 | 7 | 7 |
| Integration | `test_db_integrity.py` | 66 | 12 | 78 |
| **Total Phase 5** | | **0** | **47** | **47** |
| **Grand total** | | **176** | **47** | **~223** |

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `app/tests/test_follow_scoring.py` — 8 unit tests |
| CREATE | `app/tests/test_paper_trading.py` — 12 unit tests |
| CREATE | `app/tests/test_api/test_follow_endpoints.py` — 8 API tests |
| CREATE | `app/tests/test_api/test_portfolio_endpoints.py` — 7 API tests |
| EDIT | `app/tests/test_db_integrity.py` — add 12 integration tests, update ROW_THRESHOLDS |

---

## Verification

```bash
# Run all Phase 5 tests
python -m pytest app/tests/test_follow_scoring.py -v
python -m pytest app/tests/test_paper_trading.py -v
python -m pytest app/tests/test_api/test_follow_endpoints.py -v
python -m pytest app/tests/test_api/test_portfolio_endpoints.py -v

# Run full test suite (expect ~223 tests)
python -m pytest app/tests/ -v

# Run only integration tests
python -m pytest app/tests/test_db_integrity.py -m integration -v
```
