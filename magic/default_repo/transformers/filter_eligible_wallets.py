from pandas import DataFrame

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform_df(analytics: DataFrame, metadata: DataFrame, *args, **kwargs) -> DataFrame:
    if analytics.empty:
        return DataFrame()

    merged = analytics.merge(metadata[["wallet", "first_seen"]], on="wallet", how="left")

    eligible = merged[
        (merged["num_trades"].fillna(0) >= 50)
        & (merged["total_volume"].fillna(0) >= 1000)
    ].copy()

    print(f"Wallet filtering: {len(merged)} → {len(eligible)} eligible (trades>=50, volume>=1000)")
    return eligible


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
