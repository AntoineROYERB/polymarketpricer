from datetime import datetime, timedelta, timezone

from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL

DETECTION_WINDOW_MINUTES = 24 * 60  # 1440 minutes = full daily window for @daily orchestration

EXPECTED_COLUMNS = [
    "wallet", "market_id", "shares_before", "shares_after",
    "pnl_change",
    "market_question", "liquidity_usd", "category",
]


@data_loader
def load_data(*args, **kwargs) -> DataFrame:
    """Load recent position changes from position_history."""
    engine = create_engine(DATABASE_URL)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=DETECTION_WINDOW_MINUTES)

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                ph.wallet,
                ph.market_id,
                ph.shares_before,
                ph.shares_after,
                COALESCE(ph.pnl_change, 0) AS pnl_change,
                m.question AS market_question,
                m.liquidity_usd,
                COALESCE(m.mapped_category, m.category, 'unknown') AS category
            FROM position_history ph
            JOIN markets m ON m.id = ph.market_id
            WHERE ph.recorded_at >= :cutoff
            ORDER BY ph.recorded_at DESC
        """), {"cutoff": cutoff}).mappings().all()

    engine.dispose()

    if not rows:
        return DataFrame(columns=EXPECTED_COLUMNS)

    df = DataFrame([dict(r) for r in rows])
    print(f"Loaded {len(df)} position changes")
    return df


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
