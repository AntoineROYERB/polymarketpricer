from datetime import datetime, timezone, timedelta
from pandas import DataFrame, to_datetime

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform_df(analytics: DataFrame, metadata: DataFrame, *args, **kwargs) -> DataFrame:
    if analytics.empty:
        return DataFrame()

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    merged = analytics.merge(metadata[["wallet", "first_seen"]], on="wallet", how="left")
    merged["first_seen"] = to_datetime(merged["first_seen"], errors="coerce", utc=True)

    eligible = merged[
        (merged["num_trades"].fillna(0) >= 50)
        & (merged["total_volume"].fillna(0) >= 1000)
        & ((merged["first_seen"].notna() & (merged["first_seen"] <= cutoff)) | merged["first_seen"].isna())
    ].copy()

    print(f"Wallet filtering: {len(merged)} → {len(eligible)} eligible (trades>=50, volume>=1000, age>=3mo)")
    return eligible


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
