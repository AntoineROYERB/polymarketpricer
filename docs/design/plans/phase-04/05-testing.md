# Phase 4 — Edge Scoring — Testing

> **Goal**: Verify edge computation logic, API endpoints, and database integrity for edge scoring tables.
> **AI Agent Instructions**: Add unit tests for `compute_trade_edge.py`, API tests for new endpoints, and integration tests for `wallet_edge_snapshots`.

---

## 1. Unit Tests — `compute_trade_edge`

New test file: `magic/default_repo/tests/test_compute_trade_edge.py` (or `app/tests/test_edge_scoring.py` for pure logic tests).

### Scenarios (~10 tests)

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | `test_buy_hold_to_resolution_win` | BUY at 0.40, outcome wins (resolution_price = 1.0), no SELL | `edge = (1.0 - 0.40) / 0.40 = 1.50` |
| 2 | `test_buy_hold_to_resolution_loss` | BUY at 0.60, outcome loses (resolution_price = 0.0), no SELL | `edge = (0.0 - 0.60) / 0.60 = -1.0` |
| 3 | `test_buy_then_sell_before_resolution` | BUY at 0.30, SELL at 0.55, market resolved unknown | `edge = (0.55 - 0.30) / 0.30 = 0.8333` |
| 4 | `test_multiple_buys_fifo_matching` | 2 BUYs (0.30, 0.40), 1 SELL (0.50) — first BUY matched | BUY1 edge = (0.50 - 0.30)/0.30 = 0.67, BUY2 holds to resolution |
| 5 | `test_edge_equals_zero` | BUY at 0.50, SELL at 0.50 | `edge = 0.0` — counted as negative in consistency |
| 6 | `test_sell_without_buy_ignored` | SELL at 0.80, no prior BUY for same wallet+market+outcome | Trade skipped, no edge computed |
| 7 | `test_zero_entry_price_skipped` | BUY at 0.0 price | Trade skipped (division by zero guard) |
| 8 | `test_aggregation_correctness` | 3 trades: edges = [0.5, -0.3, 0.2] | avg=0.1333, consistency=0.6667 (2/3 positive), volatility=stdev |
| 9 | `test_min_max_normalisation` | Wallets A (avg=0.5), B (avg=0.3), C (avg=-0.2) | A score=1.0, B score=0.714, C score=0.0 |
| 10 | `test_empty_trades_returns_empty` | No trades on resolved markets | Empty DataFrame with correct columns |

### Test Implementation (pseudocode)

```python
import pytest
from datetime import datetime
from pandas import DataFrame
from decimal import Decimal

from magic.default_repo.transformers.compute_trade_edge import (
    resolve_price,
    compute_wallet_edge,
)


def make_trade(
    trade_id: str,
    wallet: str,
    market_id: str,
    outcome_id: str,
    type: str,
    price: float,
    size: float = 100.0,
    created_at: str = "2026-01-01",
) -> dict:
    return {
        "trade_id": trade_id,
        "wallet": wallet,
        "market_id": market_id,
        "outcome_id": outcome_id,
        "type": type,
        "price": price,
        "size": size,
        "amount_usd": price * size,
        "shares": size,
        "created_at": created_at,
        "market_question": "Test market?",
        "resolution": None,
        "resolution_source": None,
        "outcome_label": "Yes",
        "outcome_winner": None,
    }


def make_outcome(
    outcome_id: str, market_id: str, outcome: str, winner: bool | None
) -> dict:
    return {
        "outcome_id": outcome_id,
        "market_id": market_id,
        "outcome": outcome,
        "winner": winner,
    }


class TestComputeTradeEdge:
    """Pure unit tests for edge computation logic."""

    def test_buy_hold_to_resolution_win(self):
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.40),
        ])
        outcomes = DataFrame([
            make_outcome("o1", "m1", "Yes", True),
        ])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 1
        assert results[0]["edge"] == pytest.approx(1.50, rel=1e-3)
        assert results[0]["is_positive"] is True
        assert results[0]["had_sell"] is False

    def test_buy_hold_to_resolution_loss(self):
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o2", "BUY", 0.60),
        ])
        outcomes = DataFrame([
            make_outcome("o2", "m1", "No", False),
        ])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 1
        assert results[0]["edge"] == pytest.approx(-1.0, rel=1e-3)
        assert results[0]["is_positive"] is False

    def test_buy_then_sell(self):
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.30),
            make_trade("t2", "wallet_a", "m1", "o1", "SELL", 0.55),
        ])
        outcomes = DataFrame([
            make_outcome("o1", "m1", "Yes", True),
        ])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 1
        assert results[0]["edge"] == pytest.approx(0.8333, rel=1e-3)
        assert results[0]["had_sell"] is True
        assert results[0]["edge_price"] == pytest.approx(0.55, rel=1e-3)

    def test_multiple_buys_fifo_matching(self):
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.30),
            make_trade("t2", "wallet_a", "m1", "o1", "BUY", 0.40),
            make_trade("t3", "wallet_a", "m1", "o1", "SELL", 0.50),
        ])
        outcomes = DataFrame([
            make_outcome("o1", "m1", "Yes", True),
        ])
        results = compute_wallet_edge(trades, outcomes)
        # BUY1 (0.30) matched to SELL (0.50) → edge = 0.6667
        # BUY2 (0.40) held to resolution (1.0) → edge = 1.50
        assert len(results) == 2
        buy1 = [r for r in results if r["entry_price"] == 0.30][0]
        buy2 = [r for r in results if r["entry_price"] == 0.40][0]
        assert buy1["edge"] == pytest.approx(0.6667, rel=1e-3)
        assert buy2["edge"] == pytest.approx(1.50, rel=1e-3)

    def test_edge_zero_counts_as_negative(self):
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.50),
            make_trade("t2", "wallet_a", "m1", "o1", "SELL", 0.50),
        ])
        outcomes = DataFrame([
            make_outcome("o1", "m1", "Yes", True),
        ])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 1
        assert results[0]["edge"] == pytest.approx(0.0, abs=1e-6)
        assert results[0]["is_positive"] is False

    def test_sell_without_buy_ignored(self):
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "SELL", 0.80),
        ])
        outcomes = DataFrame([
            make_outcome("o1", "m1", "Yes", True),
        ])
        results = compute_wallet_edge(trades, outcomes)
        assert len(results) == 0

    def test_aggregation_correctness(self):
        """Integration of compute_wallet_edge + aggregation logic."""
        from magic.default_repo.transformers.compute_trade_edge import (
            compute_edges,
        )
        trades = DataFrame([
            make_trade("t1", "wallet_a", "m1", "o1", "BUY", 0.50, size=100),
            make_trade("t2", "wallet_a", "m1", "o1", "SELL", 0.75, size=100),
            make_trade("t3", "wallet_a", "m2", "o2", "BUY", 0.40, size=100),
            make_trade("t4", "wallet_a", "m2", "o2", "BUY", 0.30, size=100),
        ])
        outcomes = DataFrame([
            make_outcome("o1", "m1", "Yes", True),
            make_outcome("o2", "m2", "No", False),
        ])
        result = compute_edges(trades, outcomes)
        assert len(result) == 1  # One wallet
        row = result.iloc[0]
        assert row["num_edge_trades"] == 3
        # BUY1→SELL: edge = 0.50
        # BUY2→resolution(0.0): edge = -1.0
        # BUY3→resolution(0.0): edge = -1.0
        # avg = (0.50 + (-1.0) + (-1.0)) / 3 = -0.50
        assert row["avg_edge"] == pytest.approx(-0.50, rel=1e-3)
        assert row["positive_edge_trades"] == 1
        assert row["negative_edge_trades"] == 2
```

---

## 2. API Tests — New Endpoints (~6 tests)

New file or add to existing test files:

### `app/tests/test_api/test_edge_endpoints.py` (NEW)

| # | Test | What it validates |
|---|------|-------------------|
| 1 | `test_edge_leaderboard_empty` | 200 with empty data list when no edge data exists |
| 2 | `test_edge_leaderboard_with_data` | 200 with correct shape, rank order, score range [0,1] |
| 3 | `test_edge_leaderboard_pagination` | limit/offset reflected in response |
| 4 | `test_edge_leaderboard_invalid_limit` | 422 for limit=999 |
| 5 | `test_wallet_edge_success` | 200 with edge metrics for known wallet |
| 6 | `test_wallet_edge_not_found` | 404 for non-existent wallet |

These use the same `AsyncMock` pattern from Phase 1/2 conftest.

---

## 3. Integration Tests — Add to `test_db_integrity.py` (~8 tests)

New tests appended to the existing file using the same `conn` fixture pattern:

```python
# ── Phase 4: Edge Scoring ──────────────────────────────────────────


def test_wallet_edge_snapshots_queryable(conn: Connection) -> None:
    """wallet_edge_snapshots table exists and is queryable."""
    count: int = conn.execute(
        text("SELECT COUNT(*) FROM wallet_edge_snapshots")
    ).scalar() or 0
    assert count >= 0, "wallet_edge_snapshots query failed"


def test_wallet_edge_snapshots_fk(conn: Connection) -> None:
    """No orphaned wallet foreign keys in wallet_edge_snapshots."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM wallet_edge_snapshots wes "
            "LEFT JOIN wallets w ON w.wallet = wes.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar() or 0
    assert count == 0, (
        f"Found {count} edge snapshots referencing non-existent wallets"
    )


def test_wallet_edge_snapshots_not_null(conn: Connection) -> None:
    """Critical columns (wallet, snapshot_date, avg_edge, num_edge_trades)
    have no NULLs."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM wallet_edge_snapshots "
            "WHERE wallet IS NULL "
            "   OR snapshot_date IS NULL "
            "   OR avg_edge IS NULL "
            "   OR num_edge_trades IS NULL"
        )
    ).scalar() or 0
    assert count == 0, (
        f"Found {count} edge snapshots with NULL in critical columns"
    )


def test_wallet_edge_snapshots_score_range(conn: Connection) -> None:
    """edge_score must be in [0, 1]."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM wallet_edge_snapshots "
            "WHERE edge_score < 0 OR edge_score > 1"
        )
    ).scalar() or 0
    assert count == 0, (
        f"Found {count} edge snapshots with edge_score outside [0, 1]"
    )


def test_wallet_edge_snapshots_consistency_range(conn: Connection) -> None:
    """edge_consistency must be in [0, 1]."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM wallet_edge_snapshots "
            "WHERE edge_consistency < 0 OR edge_consistency > 1"
        )
    ).scalar() or 0
    assert count == 0, (
        f"Found {count} edge snapshots with edge_consistency outside [0, 1]"
    )


def test_wallet_edge_snapshots_volatility_non_negative(conn: Connection) -> None:
    """edge_volatility must be >= 0."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM wallet_edge_snapshots "
            "WHERE edge_volatility < 0"
        )
    ).scalar() or 0
    assert count == 0, (
        f"Found {count} edge snapshots with negative edge_volatility"
    )


def test_wallet_edge_snapshots_avg_edge_bounds(conn: Connection) -> None:
    """avg_edge must be within reasonable bounds (e.g. -100 to +100)."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM wallet_edge_snapshots "
            "WHERE avg_edge < -100 OR avg_edge > 100"
        )
    ).scalar() or 0
    assert count == 0, (
        f"Found {count} edge snapshots with avg_edge outside [-100, 100]"
    )


def test_wallet_analytics_edge_score_column(conn: Connection) -> None:
    """wallet_analytics has edge_score column."""
    result: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'wallet_analytics' "
            "AND column_name = 'edge_score'"
        )
    ).scalar() or 0
    assert result == 1, "edge_score column missing from wallet_analytics"


def test_ranking_snapshots_edge_score_column(conn: Connection) -> None:
    """ranking_snapshots has edge_score column."""
    result: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'ranking_snapshots' "
            "AND column_name = 'edge_score'"
        )
    ).scalar() or 0
    assert result == 1, "edge_score column missing from ranking_snapshots"
```

---

## 4. Row Thresholds Update

Update `ROW_THRESHOLDS` in `test_db_integrity.py`:

```python
ROW_THRESHOLDS: dict[str, int] = {
    "wallets": 1000,
    "markets": 500,
    "events": 100,
    "outcomes": 500,
    "trades": 5000,
    "positions": 500,
    "position_history": 1000,
    "wallet_analytics": 200,
    "ranking_snapshots": 200,
    "category_analytics": 100,
    "category_rankings": 50,
    "alerts": 0,              # Phase 3 — may be empty
    "wallet_pnl_snapshots": 100,
    "wallet_edge_snapshots": 50,   # Phase 4 — at least 50 wallets have edge data
}
```

---

## 5. Expected Test Counts

| Suite | File | Tests |
|-------|------|-------|
| Unit (edge logic) | `test_edge_scoring.py` (NEW) | **~10** |
| API (edge endpoints) | `test_api/test_edge_endpoints.py` (NEW) | **~6** |
| Integration | `test_db_integrity.py` (+9 new) | 56 → **65** |
| **Total added** | | **~25** |
| **Grand total** | | **~174** |

---

## 6. Regression & Migration Verification

```bash
# Run all tests — must all still pass
python -m pytest app/tests/ -v

# Run Phase 4 unit tests only
python -m pytest app/tests/test_edge_scoring.py -v

# Run Phase 4 API tests only
python -m pytest app/tests/test_api/test_edge_endpoints.py -v

# Run only integration tests (requires running PostgreSQL)
python -m pytest app/tests/test_db_integrity.py -m integration -v

# Verify migration forward+backward
alembic upgrade head          # apply 008_add_edge_scoring
alembic downgrade -1          # drop edge_score columns + wallet_edge_snapshots
alembic upgrade head          # re-apply — no errors
python -m pytest app/tests/ -v  # all ~174 pass
```

---

## Files to Create / Modify

| Action | Path | Detail |
|--------|------|--------|
| CREATE | `app/tests/test_edge_scoring.py` | ~10 unit tests for edge computation |
| CREATE | `app/tests/test_api/test_edge_endpoints.py` | ~6 API tests |
| EDIT | `app/tests/test_db_integrity.py` | Append 9 integration tests + update ROW_THRESHOLDS |
