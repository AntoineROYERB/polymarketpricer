"""Export global follow_score to wallet_analytics table."""

from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL

UPDATE_SQL = """
UPDATE wallet_analytics
SET follow_score = :score
WHERE wallet = :wallet
  AND snapshot_date = CURRENT_DATE
"""


@data_exporter
def export_follow_scores(df: DataFrame, *args, **kwargs) -> None:
    """Update wallet_analytics with follow_score."""
    if df.empty:
        print("No follow scores to export")
        return

    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text(UPDATE_SQL),
                {"wallet": row["wallet"], "score": float(row["follow_score"])},
            )
    engine.dispose()
    print(f"Exported follow_score for {len(df)} wallets")


@test
def test_output(*args) -> None:
    pass
