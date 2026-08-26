"""Integration tests for Phase 3-5 database content after ETL pipeline runs.

These tests connect to the real database and validate:
- Smart money detection tables (alerts, alert_rules)
- Edge scoring tables (wallet_edge_snapshots)
- Follow & paper trading tables (wallet_follows, paper_portfolios, etc.)
- Category follow scores (wallet_category_follow_scores)
"""

from collections.abc import Generator

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


# ── Phase 3: Smart Money Detection ──────────────────────────────────


def test_alerts_table_queryable(conn: Connection) -> None:
    count: int = conn.execute(text("SELECT COUNT(*) FROM alerts")).scalar() or 0
    assert count >= 0, "Alerts table query failed"


def test_alert_rules_global_default(conn: Connection) -> None:
    count: int = conn.execute(
        text("SELECT COUNT(*) FROM alert_rules WHERE wallet IS NULL")
    ).scalar() or 0
    assert count >= 1, "Global default alert rule must exist in alert_rules"


def test_alerts_fk_wallet(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM alerts a "
            "LEFT JOIN wallets w ON w.wallet = a.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"Found {count} alerts referencing non-existent wallets"


def test_alerts_fk_market(conn: Connection) -> None:
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM alerts a "
            "LEFT JOIN markets m ON m.id = a.market_id "
            "WHERE m.id IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"Found {count} alerts referencing non-existent markets"


def test_alerts_not_null_critical_columns(conn: Connection) -> None:
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
    count: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM alerts "
            "WHERE wallet_score < 0 OR wallet_score > 100"
        )
    ).scalar() or 0
    assert count == 0, f"Found {count} alerts with wallet_score outside [0, 100]"


def test_alerts_position_size_positive(conn: Connection) -> None:
    count: int = conn.execute(
        text("SELECT COUNT(*) FROM alerts WHERE position_size <= 0")
    ).scalar() or 0
    assert count == 0, f"Found {count} alerts with non-positive position_size"


def test_alerts_valid_actions(conn: Connection) -> None:
    rows = conn.execute(
        text(
            "SELECT DISTINCT action FROM alerts "
            "WHERE action NOT IN "
            "('NEW_POSITION', 'POSITION_INCREASE', 'POSITION_DECREASE', 'FULL_EXIT')"
        )
    ).fetchall()
    assert len(rows) == 0, f"Found invalid alert actions: {rows}"


# ── Phase 4: Edge Scoring ──────────────────────────────────────────


def test_wallet_edge_snapshots_queryable(conn: Connection) -> None:
    count: int = conn.execute(
        text("SELECT COUNT(*) FROM wallet_edge_snapshots")
    ).scalar() or 0
    assert count >= 0, "wallet_edge_snapshots query failed"


def test_wallet_edge_snapshots_fk(conn: Connection) -> None:
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
    result: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'wallet_analytics' "
            "AND column_name = 'edge_score'"
        )
    ).scalar() or 0
    assert result == 1, "edge_score column missing from wallet_analytics"


def test_ranking_snapshots_edge_score_column(conn: Connection) -> None:
    result: int = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'ranking_snapshots' "
            "AND column_name = 'edge_score'"
        )
    ).scalar() or 0
    assert result == 1, "edge_score column missing from ranking_snapshots"


# ── Phase 5: Follow & Paper Trading ──────────────────────────────────


class TestPhase05Follow:
    """Integration tests for Phase 5 wallet_follows table."""

    def test_wallet_follows_queryable(self, conn: Connection) -> None:
        cur = conn.execute(text("SELECT COUNT(*) FROM wallet_follows"))
        count = cur.scalar() or 0
        assert count >= 0

    def test_wallet_follows_fk_wallet(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_follows wf "
            "LEFT JOIN wallets w ON w.wallet = wf.wallet "
            "WHERE w.wallet IS NULL"
        )).scalar() or 0
        assert count == 0, f"Found {count} orphan wallet_follows rows"

    def test_wallet_follows_not_null(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_follows "
            "WHERE wallet IS NULL OR user_id IS NULL"
        )).scalar() or 0
        assert count == 0

    def test_wallet_follows_active_valid(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_follows "
            "WHERE active NOT IN (true, false)"
        )).scalar() or 0
        assert count == 0


class TestPhase05PaperTrading:
    """Integration tests for Phase 5 paper_trading tables."""

    def test_paper_portfolios_queryable(self, conn: Connection) -> None:
        count = conn.execute(text("SELECT COUNT(*) FROM paper_portfolios")).scalar() or 0
        assert count >= 0

    def test_paper_positions_queryable(self, conn: Connection) -> None:
        count = conn.execute(text("SELECT COUNT(*) FROM paper_positions")).scalar() or 0
        assert count >= 0

    def test_paper_trades_queryable(self, conn: Connection) -> None:
        count = conn.execute(text("SELECT COUNT(*) FROM paper_trades")).scalar() or 0
        assert count >= 0

    def test_paper_positions_not_null(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM paper_positions "
            "WHERE portfolio_id IS NULL OR market_id IS NULL "
            "OR shares IS NULL OR avg_entry_price IS NULL"
        )).scalar() or 0
        assert count == 0

    def test_paper_positions_status_valid(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM paper_positions "
            "WHERE status NOT IN ('OPEN', 'CLOSED', 'RESOLVED')"
        )).scalar() or 0
        assert count == 0

    def test_paper_portfolios_balance_non_negative(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM paper_portfolios WHERE current_balance < 0"
        )).scalar() or 0
        assert count == 0


class TestPhase05FollowScore:
    """Integration tests for follow_score on wallet_analytics."""

    def test_follow_score_column_exists(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'wallet_analytics' "
            "AND column_name = 'follow_score'"
        )).scalar() or 0
        assert count == 1

    def test_follow_score_range(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_analytics "
            "WHERE follow_score IS NOT NULL "
            "AND (follow_score < 0 OR follow_score > 1)"
        )).scalar() or 0
        assert count == 0, f"Found {count} out-of-range follow_scores"

    def test_category_follow_scores_column_exists(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'wallet_analytics' "
            "AND column_name = 'category_follow_scores'"
        )).scalar() or 0
        assert count == 1


class TestPhase05CategoryFollowScores:
    """Integration tests for wallet_category_follow_scores table."""

    def test_wallet_category_follow_scores_queryable(self, conn: Connection) -> None:
        count = conn.execute(
            text("SELECT COUNT(*) FROM wallet_category_follow_scores")
        ).scalar() or 0
        assert count >= 0

    def test_wallet_category_follow_scores_fk_wallet(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_category_follow_scores wcfs "
            "LEFT JOIN wallets w ON w.wallet = wcfs.wallet "
            "WHERE w.wallet IS NULL"
        )).scalar() or 0
        assert count == 0

    def test_wallet_category_follow_scores_fk_category(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_category_follow_scores wcfs "
            "LEFT JOIN categories c ON c.category = wcfs.category "
            "WHERE c.category IS NULL"
        )).scalar() or 0
        assert count == 0

    def test_wallet_category_follow_scores_not_null(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_category_follow_scores "
            "WHERE wallet IS NULL OR category IS NULL "
            "OR snapshot_date IS NULL "
            "OR follow_score IS NULL "
            "OR recommendation IS NULL"
        )).scalar() or 0
        assert count == 0

    def test_wallet_category_follow_scores_score_range(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_category_follow_scores "
            "WHERE follow_score < 0 OR follow_score > 1"
        )).scalar() or 0
        assert count == 0

    def test_wallet_category_follow_scores_valid_recommendation(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_category_follow_scores "
            "WHERE recommendation NOT IN ('FOLLOW', 'WATCH', 'IGNORE')"
        )).scalar() or 0
        assert count == 0

    def test_wallet_category_follow_scores_is_specialist_bool(self, conn: Connection) -> None:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM wallet_category_follow_scores "
            "WHERE is_specialist NOT IN (true, false)"
        )).scalar() or 0
        assert count == 0
