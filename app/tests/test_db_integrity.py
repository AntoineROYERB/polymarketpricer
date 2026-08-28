"""Integration tests verifying database content after ETL pipeline runs.

These tests connect to the real database and validate:
- Row count thresholds for all tables
- Referential integrity (no orphaned FK references)
- Not-null constraints on critical columns
- Data quality ranges on wallet_analytics
- Date / timestamp sanity
"""

import os
from collections.abc import Generator
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.config import settings

pytestmark = pytest.mark.integration

SYNC_URL = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
_engine = create_engine(SYNC_URL)


@pytest.fixture
def conn() -> Generator[Connection, None, None]:
    c = _engine.connect()
    try:
        yield c
    finally:
        c.rollback()
        c.close()


# The sampled seed committed to the repo (docker/initdb/seed.sql.gz) carries a
# 200-wallet slice of the production database, so volume assertions come in two
# tiers: floors every dataset must clear, and production-scale thresholds that
# only hold after a full ETL run (FULL_DATASET=1).
FULL_DATASET = os.getenv("FULL_DATASET", "").lower() in {"1", "true", "yes"}

# ── Minimum expected rows per table (sampled seed and up) ────────────
ROW_THRESHOLDS = {
    "events": 100,
    "markets": 500,
    "outcomes": 1_000,
    "wallets": 100,
    "positions": 100,
    "trades": 5_000,
    "wallet_analytics": 61,
    "ranking_snapshots": 85,
    "category_analytics": 100,
    "category_rankings": 100,
    "wallet_pnl_snapshots": 100,
    "wallet_edge_snapshots": 50,
    # Populated by the follow / paper-trading pipelines; may be empty in a seed
    "wallet_follows": 0,
    "paper_portfolios": 0,
    "paper_positions": 0,
    "paper_trades": 0,
    "wallet_category_follow_scores": 0,
}

# ── Volumes expected only after a full ETL run ───────────────────────
FULL_DATASET_THRESHOLDS = {
    "events": 10_000,
    "markets": 50_000,
    "outcomes": 100_000,
    "wallets": 1_000,
    "positions": 5_000,
    "trades": 50_000,
}

EMPTY_TABLES: set[str] = set()  # every table above is populated by the pipelines


@pytest.mark.parametrize("tbl,min_rows", list(ROW_THRESHOLDS.items()))
def test_table_row_counts(conn: Connection, tbl: str, min_rows: int) -> None:
    count: int = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
    assert count >= min_rows, (
        f"{tbl} has {count} rows, expected at least {min_rows}"
    )


@pytest.mark.skipif(not FULL_DATASET, reason="requires a full ETL dataset (FULL_DATASET=1)")
@pytest.mark.parametrize("tbl,min_rows", list(FULL_DATASET_THRESHOLDS.items()))
def test_table_row_counts_full_dataset(
    conn: Connection, tbl: str, min_rows: int
) -> None:
    count: int = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
    assert count >= min_rows, (
        f"{tbl} has {count} rows, expected at least {min_rows}"
    )


@pytest.mark.parametrize("tbl", list(EMPTY_TABLES))
def test_empty_tables_stay_empty(conn: Connection, tbl: str) -> None:
    count: int = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
    assert count == 0, f"Expected {tbl} to be empty, found {count} rows"


# ── Referential integrity ────────────────────────────────────────────
FK_CHECKS = [
    ("positions", "wallets", "wallet", "wallet"),
    ("positions", "markets", "market_id", "id"),
    ("trades", "wallets", "wallet", "wallet"),
    ("trades", "markets", "market_id", "id"),
    ("wallet_analytics", "wallets", "wallet", "wallet"),
    ("category_analytics", "wallets", "wallet", "wallet"),
    ("category_rankings", "wallets", "wallet", "wallet"),
    ("wallet_pnl_snapshots", "wallets", "wallet", "wallet"),
]


@pytest.mark.parametrize(
    ("child_tbl", "parent_tbl", "child_col", "parent_col"),
    FK_CHECKS,
    ids=[f"{c}.{cc} → {p}.{pc}" for c, p, cc, pc in FK_CHECKS],
)
def test_referential_integrity(
    conn: Connection,
    child_tbl: str,
    parent_tbl: str,
    child_col: str,
    parent_col: str,
) -> None:
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


def test_market_event_reference(conn: Connection) -> None:
    count = conn.execute(
        text(
            "SELECT count(*) FROM markets m "
            "LEFT JOIN events e ON m.event_id = e.id "
            "WHERE m.event_id IS NOT NULL AND e.id IS NULL"
        )
    ).scalar()
    assert count == 0, f"{count} markets reference non-existent events"


def test_outcome_market_reference(conn: Connection) -> None:
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
    ("wallet_pnl_snapshots", "wallet"),
    ("wallet_pnl_snapshots", "snapshot_date"),
]

REQUIRED_ANALYTICS = (
    "wallet",
    "snapshot_date",
)


@pytest.mark.parametrize(
    "tbl,col", NOT_NULL_CHECKS, ids=[f"{t}.{c}" for t, c in NOT_NULL_CHECKS]
)
def test_not_null_critical_columns(conn: Connection, tbl: str, col: str) -> None:
    count: int = conn.execute(
        text(f"SELECT count(*) FROM {tbl} WHERE {col} IS NULL")
    ).scalar() or 0
    assert count == 0, f"{tbl}.{col} has {count} NULL values"


def test_analytics_critical_not_null(conn: Connection) -> None:
    for col in REQUIRED_ANALYTICS:
        count: int = conn.execute(
            text(f"SELECT count(*) FROM wallet_analytics WHERE {col} IS NULL")
        ).scalar() or 0
        assert count == 0, f"wallet_analytics.{col} has {count} NULL values"


# ── wallet_analytics data quality ────────────────────────────────────
def test_analytics_snapshot_date_is_today(conn: Connection) -> None:
    today = date.today()
    dates = conn.execute(
        text("SELECT DISTINCT snapshot_date FROM wallet_analytics")
    ).scalars().all()
    for d in dates:
        assert d <= today, f"Found future snapshot_date {d} (max allowed: {today})"


def test_analytics_pnl_is_reasonable(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE total_pnl > 500000 OR total_pnl < -500000"
        )
    ).scalar() or 0
    assert count == 0, f"{count} wallets have extreme total_pnl outside ±500k"


def test_analytics_win_rate_range(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE win_rate IS NOT NULL AND (win_rate < 0 OR win_rate > 1)"
        )
    ).scalar() or 0
    assert count == 0, f"{count} wallets have win_rate outside [0, 1]"


def test_analytics_wallet_score_range(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE wallet_score IS NOT NULL AND (wallet_score < 0 OR wallet_score > 100)"
        )
    ).scalar() or 0
    assert count == 0, f"{count} wallets have wallet_score outside [0, 100]"


def test_analytics_max_drawdown_non_positive(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE max_drawdown IS NOT NULL AND max_drawdown > 0"
        )
    ).scalar() or 0
    assert count == 0, f"{count} wallets have positive max_drawdown"


def test_analytics_profit_factor_non_negative(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics "
            "WHERE profit_factor IS NOT NULL AND profit_factor < 0"
        )
    ).scalar() or 0
    assert count == 0, f"{count} wallets have negative profit_factor"


# ── Category analytics data quality ────────────────────────────────
def test_category_analytics_snapshot_date_is_today(conn: Connection) -> None:
    today = date.today()
    dates = conn.execute(
        text("SELECT DISTINCT snapshot_date FROM category_analytics")
    ).scalars().all()
    for d in dates:
        assert d <= today, f"Found future snapshot_date {d} (max allowed: {today})"


def test_category_analytics_win_rate_range(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM category_analytics "
            "WHERE win_rate IS NOT NULL AND (win_rate < 0 OR win_rate > 1)"
        )
    ).scalar() or 0
    assert count == 0, f"{count} rows have win_rate outside [0, 1]"


def test_category_ranking_wallets_subset_of_wallets(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM category_rankings cr "
            "LEFT JOIN wallets w ON cr.wallet = w.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"{count} ranking wallets not in wallets table"


def test_category_analytics_wallets_subset_of_wallets(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM category_analytics ca "
            "LEFT JOIN wallets w ON ca.wallet = w.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"{count} analytics wallets not in wallets table"


def test_category_analytics_not_null(conn: Connection) -> None:
    for col in ("wallet", "category", "snapshot_date"):
        count: int = conn.execute(
            text(f"SELECT count(*) FROM category_analytics WHERE {col} IS NULL")
        ).scalar() or 0
        assert count == 0, f"category_analytics.{col} has {count} NULL values"


def test_category_analytics_roi_range(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM category_analytics "
            "WHERE roi IS NOT NULL AND (roi < -100000.0 OR roi > 500000.0)"
        )
    ).scalar() or 0
    assert count == 0, f"{count} rows have roi outside [-100000.0, 500000.0]"


# ── wallet_pnl_snapshots data quality ───────────────────────────────
def test_pnl_snapshot_consistency(conn: Connection) -> None:
    rows = conn.execute(
        text("""
            SELECT COUNT(*) FROM wallet_pnl_snapshots
            WHERE total_pnl IS NOT NULL
              AND total_realized_pnl IS NOT NULL
              AND total_unrealized_pnl IS NOT NULL
              AND ABS(total_pnl - (total_realized_pnl + total_unrealized_pnl)) > 0.01
        """)
    ).scalar() or 0
    assert rows == 0, f"{rows} rows have mismatched total_pnl"


def test_pnl_snapshot_bounds(conn: Connection) -> None:
    rows = conn.execute(
        text("""
            SELECT COUNT(*) FROM wallet_pnl_snapshots wps
            JOIN wallet_analytics wa ON wps.wallet = wa.wallet
                AND wps.snapshot_date = wa.snapshot_date
            WHERE wa.total_cost_basis > 0
              AND ABS(wps.total_pnl) > 100 * wa.total_cost_basis
        """)
    ).scalar() or 0
    assert rows == 0, f"{rows} rows have PnL > 100x cost basis"


# ── Timestamp sanity ─────────────────────────────────────────────────
def test_no_future_timestamps_in_trades(conn: Connection) -> None:
    now = datetime.now(timezone.utc)
    count: int = conn.execute(
        text("SELECT count(*) FROM trades WHERE timestamp > :now"),
        {"now": now},
    ).scalar() or 0
    assert count == 0, f"{count} trades have future timestamps"


def test_no_future_dates_in_analytics(conn: Connection) -> None:
    today = date.today()
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics WHERE snapshot_date > :today"
        ),
        {"today": today},
    ).scalar() or 0
    assert count == 0, f"{count} analytics rows have future snapshot_date"


# ── Cross-table consistency ──────────────────────────────────────────
def test_analytics_wallets_subset_of_wallets(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM wallet_analytics wa "
            "LEFT JOIN wallets w ON wa.wallet = w.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"{count} analytics wallets not in wallets table"


def test_trade_wallets_subset_of_wallets(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT count(DISTINCT t.wallet) FROM trades t "
            "LEFT JOIN wallets w ON t.wallet = w.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"{count} trade wallets not in wallets table"


def test_markets_have_at_least_one_outcome(conn: Connection) -> None:
    orphans: int = conn.execute(
        text(
            "SELECT count(*) FROM markets m "
            "LEFT JOIN outcomes o ON m.id = o.market_id "
            "WHERE o.id IS NULL"
        )
    ).scalar() or 0
    assert orphans == 0, f"{orphans} markets have no outcomes"

