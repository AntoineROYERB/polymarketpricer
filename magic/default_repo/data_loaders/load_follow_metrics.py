"""Load all metrics needed for global and per-category follow scoring."""

from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL

GLOBAL_METRICS_QUERY = """
WITH wallet_metrics AS (
    SELECT
        wa.wallet,
        -- Edge score (from wallet_edge_snapshots, latest)
        COALESCE(wes.edge_score, 0) AS edge_score,
        -- Consistency score
        COALESCE(wa.consistency_score, 0) AS consistency_score,
        -- Category specialization
        COALESCE(ca.specialist_count, 0) AS specialist_count,
        COALESCE(ca.avg_category_rank, 50) AS avg_category_rank,
        -- Recency
        COALESCE(t.days_since_last_trade, 999) AS days_since_last_trade,
        -- Trade frequency
        COALESCE(t.total_trades, 0) AS total_trades,
        COALESCE(t.months_active, 1) AS months_active
    FROM wallet_analytics wa
    LEFT JOIN (
        SELECT DISTINCT ON (wallet)
            wallet, edge_score
        FROM wallet_edge_snapshots
        ORDER BY wallet, snapshot_date DESC
    ) wes ON wes.wallet = wa.wallet
    LEFT JOIN (
        SELECT
            wallet,
            COUNT(*) FILTER (WHERE is_specialist) AS specialist_count,
            AVG(category_rank) AS avg_category_rank
        FROM category_analytics
        WHERE snapshot_date = CURRENT_DATE
        GROUP BY wallet
    ) ca ON ca.wallet = wa.wallet
    LEFT JOIN (
        SELECT
            wallet,
            (CURRENT_DATE - MAX(timestamp::date))::int
                AS days_since_last_trade,
            COUNT(*) AS total_trades,
            GREATEST(
                (CURRENT_DATE - MIN(timestamp::date)) / 30.0,
                1
            ) AS months_active
        FROM trades
        GROUP BY wallet
    ) t ON t.wallet = wa.wallet
    WHERE wa.snapshot_date = CURRENT_DATE
)
SELECT * FROM wallet_metrics
"""

CATEGORY_METRICS_QUERY = """
SELECT
    ca.wallet,
    ca.category,
    ca.roi,
    ca.win_rate,
    ca.num_trades,
    ca.total_volume,
    ca.is_specialist,
    -- Percentile ranking within category
    PERCENT_RANK() OVER (
        PARTITION BY ca.category
        ORDER BY ca.roi DESC
    ) as roi_percentile,
    PERCENT_RANK() OVER (
        PARTITION BY ca.category
        ORDER BY ca.total_volume DESC
    ) as volume_percentile,
    -- Recency in category
    (CURRENT_DATE - MAX(t.timestamp::date)) as recency_days,
    -- Global edge for context
    wes.edge_score as global_edge_score,
    -- Global follow_score for context (may be NULL if not yet computed)
    wa.follow_score as global_follow_score
FROM category_analytics ca
LEFT JOIN trades t ON t.wallet = ca.wallet
LEFT JOIN markets m ON m.id = t.market_id
    AND (m.mapped_category = ca.category OR m.category = ca.category)
LEFT JOIN (
    SELECT DISTINCT ON (wallet) wallet, edge_score
    FROM wallet_edge_snapshots
    ORDER BY wallet, snapshot_date DESC
) wes ON wes.wallet = ca.wallet
LEFT JOIN wallet_analytics wa ON wa.wallet = ca.wallet
    AND wa.snapshot_date = CURRENT_DATE
WHERE ca.snapshot_date = CURRENT_DATE
GROUP BY ca.wallet, ca.category, ca.roi, ca.win_rate, ca.num_trades,
         ca.total_volume, ca.is_specialist, wes.edge_score, wa.follow_score
"""


@data_loader
def load_follow_metrics(*args, **kwargs) -> dict[str, DataFrame]:
    """Load all metrics needed for follow scoring.

    Returns a dict with two DataFrames:
        - 'global_metrics': per-wallet metrics for global follow_score
        - 'category_metrics': per-wallet x per-category metrics for category follow scores
    """
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Global metrics
        global_result = conn.execute(text(GLOBAL_METRICS_QUERY))
        global_df = DataFrame(global_result.fetchall(), columns=global_result.keys())

        # Category metrics
        cat_result = conn.execute(text(CATEGORY_METRICS_QUERY))
        cat_df = DataFrame(cat_result.fetchall(), columns=cat_result.keys())

    engine.dispose()

    print(f"Loaded {len(global_df)} wallet records for global scoring")
    print(f"Loaded {len(cat_df)} wallet x category records for per-category scoring")

    return {
        "global_metrics": global_df,
        "category_metrics": cat_df,
    }


@test
def test_output(output: dict[str, DataFrame]) -> None:
    assert output is not None, "Output is undefined"
    assert "global_metrics" in output, "Missing global_metrics key"
    assert "category_metrics" in output, "Missing category_metrics key"

    gm = output["global_metrics"]
    assert "wallet" in gm.columns, "global_metrics missing wallet column"
    assert "edge_score" in gm.columns, "global_metrics missing edge_score column"
    assert "consistency_score" in gm.columns, "global_metrics missing consistency_score column"

    cm = output["category_metrics"]
    if not cm.empty:
        assert "wallet" in cm.columns, "category_metrics missing wallet column"
        assert "category" in cm.columns, "category_metrics missing category column"
        assert "roi_percentile" in cm.columns, "category_metrics missing roi_percentile column"
