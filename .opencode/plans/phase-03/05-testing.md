# Phase 3 — Smart Money Detection — Testing

> **Goal**: Verify alert detection, Discord delivery, WebSocket streaming, database integrity, and regression.
> **AI Agent Instructions**: Integration tests have been appended to `app/tests/test_db_integrity.py`.
> API and service-layer unit tests already exist at:
> - `app/tests/test_api/test_alert_endpoints.py` (13 tests)
> - `app/tests/test_alert_service.py` (39 tests)
> - `app/tests/test_ws_manager.py` (14 tests)

---

## 1. Unit / API Tests — Already Implemented

Mock-based tests (no real DB) exist in three files:

### `app/tests/test_api/test_alert_endpoints.py` — 13 tests

| Test | What it validates |
|------|-------------------|
| `test_alerts_empty` | 200 with empty data list |
| `test_alerts_with_limit` | Pagination limit reflected in response |
| `test_alerts_invalid_limit` | 422 for limit=999 |
| `test_alerts_negative_offset` | 422 for offset=-1 |
| `test_alerts_invalid_offset_type` | 422 for offset=abc |
| `test_alerts_category_filter` | Category filter returns 200 |
| `test_alerts_min_score_filter` | min_score filter returns 200 |
| `test_alerts_wallet_filter` | Wallet filter returns 200 |
| `test_alerts_filters_combined` | Combined filters return 200 |
| `test_alerts_wallet_not_found` | 404 for non-existent wallet |
| `test_alerts_wallet_zero_alerts` | 200 with empty data for known wallet with no alerts |
| `test_alerts_stats_empty` | Stats endpoint returns zeros and empty lists |
| `test_alerts_stats_shape` | Stats response has all required keys |

### `app/tests/test_alert_service.py` — 39 tests

| Test class | Tests | Coverage |
|---|---|---|
| `TestClassifyAction` | 11 | `classify_action()` — new, increase, decrease, full exit, no change, edge cases, negative values |
| `TestFormatAction` | 7 | `_format_action()` — all 4 action types, unknown fallback, precision, large price |
| `TestSendDiscordAlert` | 8 | `send_discord_alert()` — 200/204 success, 400/500 errors, network timeout, payload shape, color by action, unknown action color |
| `TestPollUnnotifiedAlerts` | 5 | Query logic, empty results, SQL filters (notified_at IS NULL, delivery_attempts < 3), ordering + limit |
| `TestMarkNotified` | 5 | Success sets notified_at, failure increments delivery_attempts, no-op when alert not found, UUID filter |
| `TestEdgeCases` | 3 | Happy path (send + mark), retry after failure |

### `app/tests/test_ws_manager.py` — 14 tests

| Test class | Tests | Coverage |
|---|---|---|
| `TestConnectionLifecycle` | 5 | Connect adds + accepts, disconnect removes, unknown disconnect safe, multiple connections |
| `TestBroadcastAlert` | 5 | Sends to all, payload structure, dead connection removal, no connections, partial failure |
| `TestHeartbeat` | 4 | Sends ping to one, sends to all, removes dead connections, no connections safe |

---

## 2. Integration Tests — Add to `test_db_integrity.py`

Real database tests. Appended to the existing file using the same `conn` fixture pattern.

```python
# ── Phase 3: Smart Money Detection ──────────────────────────────────


def test_alerts_table_queryable(conn: Connection) -> None:
    """Alerts table exists and is queryable."""
    count: int = conn.execute(text("SELECT COUNT(*) FROM alerts")).scalar() or 0
    assert count >= 0, "Alerts table query failed"


def test_alert_rules_global_default(conn: Connection) -> None:
    """Global default alert rule exists (wallet IS NULL)."""
    count: int = conn.execute(
        text("SELECT COUNT(*) FROM alert_rules WHERE wallet IS NULL")
    ).scalar() or 0
    assert count >= 1, "Global default alert rule must exist in alert_rules"


def test_alerts_fk_wallet(conn: Connection) -> None:
    """No orphaned wallet foreign keys in alerts."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM alerts a "
            "LEFT JOIN wallets w ON w.wallet = a.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"Found {count} alerts referencing non-existent wallets"


def test_alerts_fk_market(conn: Connection) -> None:
    """No orphaned market foreign keys in alerts."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM alerts a "
            "LEFT JOIN markets m ON m.id = a.market_id "
            "WHERE m.id IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"Found {count} alerts referencing non-existent markets"


def test_alerts_not_null_critical_columns(conn: Connection) -> None:
    """Critical columns (wallet, market_id, market_question, action, price,
    position_size, wallet_score, category) have no NULLs."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM alerts "
            "WHERE wallet IS NULL "
            "   OR market_id IS NULL "
            "   OR market_question IS NULL "
            "   OR action IS NULL "
            "   OR price IS NULL "
            "   OR position_size IS NULL "
            "   OR wallet_score IS NULL "
            "   OR category IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"Found {count} alerts with NULL in critical columns"


def test_alerts_score_range(conn: Connection) -> None:
    """wallet_score must be in [0, 100]."""
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM alerts "
            "WHERE wallet_score < 0 OR wallet_score > 100"
        )
    ).scalar() or 0
    assert count == 0, f"Found {count} alerts with wallet_score outside [0, 100]"


def test_alerts_position_size_positive(conn: Connection) -> None:
    """position_size must be strictly positive."""
    count: int = conn.execute(
        text("SELECT COUNT(*) FROM alerts WHERE position_size <= 0")
    ).scalar() or 0
    assert count == 0, f"Found {count} alerts with non-positive position_size"


def test_alerts_valid_actions(conn: Connection) -> None:
    """All action values must be valid enum members."""
    rows = conn.execute(
        text(
            "SELECT DISTINCT action FROM alerts "
            "WHERE action NOT IN "
            "('NEW_POSITION', 'POSITION_INCREASE', 'POSITION_DECREASE', 'FULL_EXIT')"
        )
    ).fetchall()
    assert len(rows) == 0, f"Found invalid alert actions: {rows}"
```

---

## 3. Service-Layer Tests — Already Implemented

### `app/tests/test_alert_service.py` — 39 tests

Covers `classify_action`, `_format_action`, `send_discord_alert`, `poll_unnotified_alerts`, `mark_notified`, and edge cases. See [section 1](#1-unit--api-tests--already-implemented) for the full breakdown.

### `app/tests/test_ws_manager.py` — 14 tests

Covers `ConnectionManager.connect`, `disconnect`, `broadcast_alert`, and `send_heartbeat`. See [section 1](#1-unit--api-tests--already-implemented) for the full breakdown.

---

## Expected Test Counts

| Suite | File | Tests |
|---|---|---|
| Unit / API | `test_api/test_endpoints.py` | 9 |
| Unit / API | `test_api/test_category_endpoints.py` | 8 |
| Unit / API | `test_api/test_alert_endpoints.py` | 13 |
| Unit / API | `test_api/test_category_classifier.py` | 10 |
| Service | `test_alert_service.py` | 39 |
| Service / WS | `test_ws_manager.py` | 14 |
| Integration | `test_db_integrity.py` | 56 (48 existing + 8 new) |
| **Total** | | **149** |

---

## Regression & Migration Verification

```bash
# Run all tests — must all still pass
python -m pytest app/tests/ -v

# Run only integration tests (requires running PostgreSQL)
python -m pytest app/tests/test_db_integrity.py -m integration -v

# Run Phase 3 unit tests only
python -m pytest app/tests/test_api/test_alert_endpoints.py app/tests/test_alert_service.py app/tests/test_ws_manager.py -v

# Verify migration forward+backward
alembic upgrade head          # apply 005_smart_money_alerts
alembic downgrade -1          # drop alerts + alert_rules
alembic upgrade head          # re-apply — no errors
python -m pytest app/tests/ -v  # all 149 pass
```

---

## Files Modified

| Action | Path | Detail |
|---|---|---|
| EDIT | `app/tests/test_db_integrity.py` | Append 8 integration tests for alerts |
