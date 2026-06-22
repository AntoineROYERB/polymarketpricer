# Phase 3 — Smart Money Detection — Testing

> **Goal**: Verify alert detection, Discord delivery, WebSocket streaming, database integrity, and regression.
> **AI Agent Instructions**: Add tests to `app/tests/test_api/test_alerts.py` (mocked), add integration tests to `app/tests/test_db_integrity.py`, and add pure unit tests for the action classifier.

---

## 1. Unit / API Tests — `app/tests/test_api/test_alerts.py`

Mock-based tests (no real DB). Uses the existing `conftest.py` pattern with `make_mock_session()`.

```python
from httpx import AsyncClient, ASGITransport
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.dependencies import get_db
from app.main import app
from app.tests.conftest import make_mock_session


@pytest.mark.asyncio
async def test_alerts_list_empty(client: AsyncClient) -> None:
    """GET /api/v1/alerts returns 200 with empty data list."""
    response = await client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_alerts_with_params(client: AsyncClient) -> None:
    """Pagination params are reflected in the response."""
    response = await client.get("/api/v1/alerts?limit=10&offset=5")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 5


@pytest.mark.asyncio
async def test_alerts_wallet_not_found(client: AsyncClient) -> None:
    """GET /api/v1/alerts/{nonexistent} returns 404."""
    response = await client.get("/api/v1/alerts/0xnonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_alerts_ws_connect() -> None:
    """WebSocket /api/v1/alerts/ws connects successfully and receives ping."""
    from fastapi.testclient import TestClient
    ws_client = TestClient(app)
    with ws_client.websocket_connect("/api/v1/alerts/ws") as ws:
        data = ws.receive_json(timeout=5)
        assert data["type"] == "ping"


@pytest.mark.asyncio
async def test_alerts_filter_category(client: AsyncClient) -> None:
    """Category filter returns 200."""
    response = await client.get("/api/v1/alerts?category=Politics")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_alerts_filter_min_score(client: AsyncClient) -> None:
    """min_score filter returns 200."""
    response = await client.get("/api/v1/alerts?min_score=80")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_alerts_stats(client: AsyncClient) -> None:
    """GET /api/v1/alerts/stats returns aggregated data."""
    response = await client.get("/api/v1/alerts/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_alerts" in data
    assert "alerts_today" in data


@pytest.mark.asyncio
async def test_alert_item_shape(client: AsyncClient) -> None:
    """Alert item contains all required fields when data is present."""
    response = await client.get("/api/v1/alerts?limit=1")
    assert response.status_code == 200
    data = response.json()
    if data["data"]:
        item = data["data"][0]
        assert "id" in item
        assert "wallet" in item
        assert "action" in item
        assert "wallet_score" in item
        assert "market_question" in item
        assert "position_size" in item
```

---

## 2. Integration Tests — Add to `test_db_integrity.py`

Real database tests. Append these to the existing file using the same `pg_conn` fixture pattern.

```python
# ── Phase 3: Smart Money Detection ──────────────────────────────────

@pytest.mark.integration
def test_alerts_table_queryable(pg_conn):
    """Alerts table exists and is queryable."""
    cur = pg_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM alerts")
    count = cur.fetchone()[0]
    assert count >= 0, "Alerts table query failed"


@pytest.mark.integration
def test_alert_rules_global_default(pg_conn):
    """Global default alert rule exists (wallet IS NULL)."""
    cur = pg_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM alert_rules WHERE wallet IS NULL")
    count = cur.fetchone()[0]
    assert count >= 1, "Global default alert rule must exist in alert_rules"


@pytest.mark.integration
def test_alerts_fk_wallet(pg_conn):
    """No orphaned wallet foreign keys in alerts."""
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM alerts a
        LEFT JOIN wallets w ON w.wallet = a.wallet
        WHERE w.wallet IS NULL
    """)
    orphans = cur.fetchone()[0]
    assert orphans == 0, f"Found {orphans} alerts referencing non-existent wallets"


@pytest.mark.integration
def test_alerts_fk_market(pg_conn):
    """No orphaned market foreign keys in alerts."""
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM alerts a
        LEFT JOIN markets m ON m.id = a.market_id
        WHERE m.id IS NULL
    """)
    orphans = cur.fetchone()[0]
    assert orphans == 0, f"Found {orphans} alerts referencing non-existent markets"


@pytest.mark.integration
def test_alerts_not_null_critical_columns(pg_conn):
    """Critical columns (wallet, market_id, action, price, position_size, wallet_score, category) have no NULLs."""
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM alerts
        WHERE wallet IS NULL
           OR market_id IS NULL
           OR action IS NULL
           OR price IS NULL
           OR position_size IS NULL
           OR wallet_score IS NULL
           OR category IS NULL
    """)
    nulls = cur.fetchone()[0]
    assert nulls == 0, f"Found {nulls} alerts with NULL in critical columns"


@pytest.mark.integration
def test_alerts_score_range(pg_conn):
    """wallet_score must be in [0, 100]."""
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM alerts
        WHERE wallet_score < 0 OR wallet_score > 100
    """)
    bad = cur.fetchone()[0]
    assert bad == 0, f"Found {bad} alerts with wallet_score outside [0, 100]"


@pytest.mark.integration
def test_alerts_position_size_positive(pg_conn):
    """position_size must be strictly positive."""
    cur = pg_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM alerts WHERE position_size <= 0")
    bad = cur.fetchone()[0]
    assert bad == 0, f"Found {bad} alerts with non-positive position_size"


@pytest.mark.integration
def test_alerts_valid_actions(pg_conn):
    """All action values must be valid enum members."""
    cur = pg_conn.cursor()
    cur.execute("""
        SELECT DISTINCT action FROM alerts
        WHERE action NOT IN ('NEW_POSITION', 'POSITION_INCREASE', 'POSITION_DECREASE', 'FULL_EXIT')
    """)
    bad = cur.fetchall()
    assert len(bad) == 0, f"Found invalid alert actions: {bad}"
```

---

## 3. Classifier / Pure Unit Tests — `app/tests/test_action_classifier.py`

Pure function tests — no DB, no mocking. Tests the `classify_action` function in isolation.

```python
import pytest
from app.services.alert_service import classify_action


class TestClassifyAction:
    """Tests for the classify_action pure function."""

    def test_new_position_from_zero(self):
        """Zero/Nothing → positive = NEW_POSITION."""
        assert classify_action(None, 100) == "NEW_POSITION"
        assert classify_action(0, 50) == "NEW_POSITION"
        assert classify_action(0, 1) == "NEW_POSITION"

    def test_increase(self):
        """Positive increase = POSITION_INCREASE."""
        assert classify_action(50, 100) == "POSITION_INCREASE"
        assert classify_action(10, 20) == "POSITION_INCREASE"
        assert classify_action(1, 5) == "POSITION_INCREASE"
        assert classify_action(1000, 2000) == "POSITION_INCREASE"

    def test_decrease(self):
        """Positive decrease (still > 0) = POSITION_DECREASE."""
        assert classify_action(100, 50) == "POSITION_DECREASE"
        assert classify_action(20, 10) == "POSITION_DECREASE"
        assert classify_action(5, 1) == "POSITION_DECREASE"

    def test_full_exit(self):
        """Positive → zero/NULL = FULL_EXIT."""
        assert classify_action(100, 0) == "FULL_EXIT"
        assert classify_action(50, None) == "FULL_EXIT"
        assert classify_action(1, 0) == "FULL_EXIT"
        assert classify_action(10, 0.0) == "FULL_EXIT"

    def test_no_change(self):
        """No meaningful change = None."""
        assert classify_action(0, 0) is None
        assert classify_action(None, None) is None
        assert classify_action(100, 100) is None
        assert classify_action(0.0, 0.0) is None

    def test_large_numbers(self):
        """Very large position changes are classified correctly."""
        assert classify_action(1e6, 1e6 + 1) == "POSITION_INCREASE"
        assert classify_action(0, 1e6) == "NEW_POSITION"
        assert classify_action(1e9, 0) == "FULL_EXIT"
```

---

## Expected Test Counts

| Suite | File | Existing | New | Total |
|---|---|---|---|---|
| Unit / API | `test_api/test_endpoints.py` | 9 | — | 9 |
| Unit / API | `test_api/test_category_endpoints.py` | 8 | — | 8 |
| Unit / API | `test_api/test_alerts.py` | — | 8 | 8 |
| Classifier | `test_action_classifier.py` | — | 6 | 6 |
| Classifier | `test_category_classifier.py` | 10 | — | 10 |
| Integration | `test_db_integrity.py` | 42 | 8 | 50 |
| **Total** | | **69** | **22** | **91** |

---

## Regression & Migration Verification

```bash
# Run all existing tests first — must all still pass
python -m pytest app/tests/ -v

# Run only new Phase 3 tests
python -m pytest app/tests/test_api/test_alerts.py app/tests/test_action_classifier.py -v

# Run only integration tests (requires running PostgreSQL)
python -m pytest app/tests/test_db_integrity.py -m integration -v

# Verify migration forward+backward
alembic upgrade head          # apply 005_smart_money_alerts
alembic downgrade -1          # drop alerts + alert_rules
alembic upgrade head          # re-apply — no errors
python -m pytest app/tests/ -v  # all 91 pass
```

---

## Files to Create / Modify

| Action | Path |
|---|---|
| CREATE | `app/tests/test_api/test_alerts.py` |
| CREATE | `app/tests/test_action_classifier.py` |
| EDIT | `app/tests/test_db_integrity.py` — append 8 integration tests |
