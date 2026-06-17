"""Integration tests verifying database content after ETL pipeline runs.

These tests connect to the real database and validate:
- Row count thresholds for all tables
- Referential integrity (no orphaned FK references)
- Not-null constraints on critical columns
- Data quality ranges on wallet_analytics
- Date / timestamp sanity
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from app.config import settings

pytestmark = pytest.mark.integration

SYNC_URL = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
_engine = create_engine(SYNC_URL)


@pytest.fixture
def conn():
    c = _engine.connect()
    yield c
    c.rollback()
    c.close()


# ── Minimum expected rows per table ──────────────────────────────────
ROW_THRESHOLDS = {
    "events": 10_000,
    "markets": 50_000,
    "outcomes": 100_000,
    "wallets": 1_000,
    "positions": 5_000,
    "trades": 50_000,
    "wallet_analytics": 100,
    "ranking_snapshots": 100,
}

EMPTY_TABLES = {"position_history"}


@pytest.mark.parametrize("tbl,min_rows", list(ROW_THRESHOLDS.items()))
def test_table_row_counts(conn, tbl: str, min_rows: int):
    count = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
    assert count >= min_rows, (
        f"{tbl} has {count} rows, expected at least {min_rows}"
    )


@pytest.mark.parametrize("tbl", list(EMPTY_TABLES))
def test_empty_tables_stay_empty(conn, tbl: str):
    count = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
    assert count == 0, f"Expected {tbl} to be empty, found {count} rows"


# ── Referential integrity ────────────────────────────────────────────
FK_CHECKS = [
    ("positions", "wallets", "wallet", "wallet"),
    ("positions", "markets", "market_id", "id"),
    ("trades", "wallets", "wallet", "wallet"),
    ("trades", "markets", "market_id", "id"),
    ("wallet_analytics", "wallets", "wallet", "wallet"),
]


@pytest.mark.parametrize(
    ("child_tbl", "parent_tbl", "child_col", "parent_col"),
    FK_CHECKS,
    ids=[f"{c}.{cc} → {p}.{pc}" for c, p, cc, pc in FK_CHECKS],
)
def test_referential_integrity(conn, child_tbl, parent_tbl, child_col, parent_col):
    count = conn.execute(
        text(
            f"SELECT count(*) FROM {child_tbl} c "
            f"LEFT JOIN {parent_tbl} p ON c.{child_col} = p.{parent_col} "
            f"WHERE p.{parent_col} IS NULL"
        )
    ).scalar()
    assert count == 0, (
        f"{count} rows in {child_tbl}.{child_col} without matching "
        f"{parent_tbl}.{parent_col}"
    )


def test_market_event_reference(conn):
    count = conn.execute(
        text(
            "SELECT count(*) FROM markets m "
            "LEFT JOIN events e ON m.event_id = e.id "
            "WHERE m.event_id IS NOT NULL AND e.id IS NULL"
        )
    ).scalar()
    assert count == 0, f"{count} markets reference non-existent events"


def test_outcome_market_reference(conn):
    count = conn.execute(
        text(
            "SELECT count(*) FROM outcomes o "
            "LEFT JOIN markets m ON o.market_id = m.id "
            "WHERE m.id IS NULL"
        )
    ).scalar()
    assert count == 0, f"{count} outcomes reference non-existent markets"


# ── Not-null constraints on critical columns ─────────────────────────
NOT_NULL_CHECKS = [
    ("markets", "question"),
    ("trades", "price"),
    ("trades", "timestamp"),
    ("wallets", "wallet"),
]

REQUIRED_ANALYTICS = (
    "wallet",
    "snapshot_date",
)


@pytest.mark.parametrize(
    "tbl,col", NOT_NULL_CHECKS, ids=[f"{t}.{c}" for t, c in NOT_NULL_CHECKS]
)
def test_not_null_critical_columns(conn, tbl: str, col: str):
    count = conn.execute(
        text(f"SELECT count(*) FROM {tbl} WHERE {col} IS NULL")
    ).scalar()
    assert count == 0, f"{tbl}.{col} has {count} NULL values"


def test_analytics_critical_not_null(conn):
    for col in REQUIRED_ANALYTICS:
        count = conn.execute(
            text(f"SELECT count(*) FROM wallet_analytics WHERE {col} IS NULL")
        ).scalar()
        assert count == 0, f"wallet_analytics.{col} has {count} NULL values"


# ── wallet_analytics data quality ────────────────────────────────────
def test_analytics_snapshot_date_is_today(conn):
    today = date.today()
    dates = conn.execute(
        text("SELECT DISTINCT snapshot_date FROM wallet_analytics")
    ).scalars().all()
    for d in dates:
        assert d == today, f"Found stale snapshot_date {d}, expected {today}"


def test_analytics_pnl_is_reasonable(conn):
    count = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE total_pnl > 500000 OR total_pnl < -500000"
        )
    ).scalar()
    assert count == 0, f"{count} wallets have extreme total_pnl outside ±500k"


def test_analytics_win_rate_range(conn):
    count = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE win_rate IS NOT NULL AND (win_rate < 0 OR win_rate > 1)"
        )
    ).scalar()
    assert count == 0, f"{count} wallets have win_rate outside [0, 1]"


def test_analytics_wallet_score_range(conn):
    count = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE wallet_score IS NOT NULL AND (wallet_score < 0 OR wallet_score > 100)"
        )
    ).scalar()
    assert count == 0, f"{count} wallets have wallet_score outside [0, 100]"


def test_analytics_max_drawdown_non_positive(conn):
    count = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE max_drawdown IS NOT NULL AND max_drawdown > 0"
        )
    ).scalar()
    assert count == 0, f"{count} wallets have positive max_drawdown"


def test_analytics_profit_factor_non_negative(conn):
    count = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE profit_factor IS NOT NULL AND profit_factor < 0"
        )
    ).scalar()
    assert count == 0, f"{count} wallets have negative profit_factor"


# ── Timestamp sanity ─────────────────────────────────────────────────
def test_no_future_timestamps_in_trades(conn):
    now = datetime.now(timezone.utc)
    count = conn.execute(
        text("SELECT count(*) FROM trades WHERE timestamp > :now"),
        {"now": now},
    ).scalar()
    assert count == 0, f"{count} trades have future timestamps"


def test_no_future_dates_in_analytics(conn):
    today = date.today()
    count = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics WHERE snapshot_date > :today"
        ),
        {"today": today},
    ).scalar()
    assert count == 0, f"{count} analytics rows have future snapshot_date"


# ── Cross-table consistency ──────────────────────────────────────────
def test_analytics_wallets_subset_of_wallets(conn):
    count = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics wa "
            "LEFT JOIN wallets w ON wa.wallet = w.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar()
    assert count == 0, f"{count} analytics wallets not in wallets table"


def test_trade_wallets_subset_of_wallets(conn):
    count = conn.execute(
        text(
            "SELECT count(DISTINCT t.wallet) FROM trades t "
            "LEFT JOIN wallets w ON t.wallet = w.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar()
    assert count == 0 or count is None, (
        f"{count} trade wallets not in wallets table"
    )


def test_markets_have_at_least_one_outcome(conn):
    count = conn.execute(
        text(
            "SELECT count(*) FROM markets m "
            "LEFT JOIN outcomes o ON m.id = o.market_id "
            "WHERE o.id IS NULL"
        )
    ).scalar()
    assert count == 0, f"{count} markets have no outcomes"
