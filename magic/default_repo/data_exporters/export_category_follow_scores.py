"""Export per-category follow scores to wallet_category_follow_scores and update wallet_analytics JSONB."""

import json
from datetime import date
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL

UPSERT_SQL = """
INSERT INTO wallet_category_follow_scores
    (wallet, category, snapshot_date, follow_score, recommendation,
     roi_percentile, win_rate, is_specialist, volume_percentile,
     recency_days, reasons, global_follow_score)
VALUES
    (:wallet, :category, :snapshot_date, :follow_score, :recommendation,
     :roi_percentile, :win_rate, :is_specialist, :volume_percentile,
     :recency_days, :reasons, :global_follow_score)
ON CONFLICT (wallet, category, snapshot_date)
DO UPDATE SET
    follow_score = EXCLUDED.follow_score,
    recommendation = EXCLUDED.recommendation,
    roi_percentile = EXCLUDED.roi_percentile,
    win_rate = EXCLUDED.win_rate,
    is_specialist = EXCLUDED.is_specialist,
    volume_percentile = EXCLUDED.volume_percentile,
    recency_days = EXCLUDED.recency_days,
    reasons = EXCLUDED.reasons,
    global_follow_score = EXCLUDED.global_follow_score
"""

UPDATE_WALLET_ANALYTICS_SQL = """
UPDATE wallet_analytics
SET category_follow_scores = CAST(:scores AS jsonb)
WHERE wallet = :wallet
  AND snapshot_date = :snapshot_date
"""


@data_exporter
def export_category_follow_scores(df: DataFrame, *args, **kwargs) -> None:
    """Export per-category follow scores.

    Input DataFrame columns:
        wallet, category, follow_score, recommendation, roi_percentile,
        win_rate, is_specialist, volume_percentile, recency_days,
        reasons, global_follow_score
    """
    if df.empty:
        print("No category follow scores to export")
        return

    engine = create_engine(DATABASE_URL)
    today = date.today()
    category_scores_by_wallet: dict[str, dict] = {}

    with engine.begin() as conn:
        for _, row in df.iterrows():
            # Upsert into wallet_category_follow_scores
            conn.execute(
                text(UPSERT_SQL),
                {
                    "wallet": row["wallet"],
                    "category": row["category"],
                    "snapshot_date": today,
                    "follow_score": float(row["follow_score"]),
                    "recommendation": row["recommendation"],
                    "roi_percentile": float(row["roi_percentile"]) if row.get("roi_percentile") is not None else None,
                    "win_rate": float(row["win_rate"]) if row.get("win_rate") is not None else None,
                    "is_specialist": bool(row.get("is_specialist", False)),
                    "volume_percentile": float(row["volume_percentile"]) if row.get("volume_percentile") is not None else None,
                    "recency_days": int(row["recency_days"]) if row.get("recency_days") is not None else None,
                    "reasons": json.dumps(row.get("reasons", [])),
                    "global_follow_score": float(row["global_follow_score"]) if row.get("global_follow_score") is not None else None,
                },
            )

            # Accumulate JSONB for wallet_analytics update
            wallet_key = row["wallet"]
            if wallet_key not in category_scores_by_wallet:
                category_scores_by_wallet[wallet_key] = {}
            category_scores_by_wallet[wallet_key][row["category"]] = {
                "follow_score": float(row["follow_score"]),
                "recommendation": row["recommendation"],
            }

        # Update wallet_analytics.category_follow_scores JSONB
        for wallet, scores in category_scores_by_wallet.items():
            conn.execute(
                text(UPDATE_WALLET_ANALYTICS_SQL),
                {
                    "wallet": wallet,
                    "snapshot_date": today,
                    "scores": json.dumps(scores),
                },
            )

    engine.dispose()
    print(f"Exported category follow scores for {len(category_scores_by_wallet)} wallets "
          f"({len(df)} total rows)")


@test
def test_output(*args) -> None:
    pass
