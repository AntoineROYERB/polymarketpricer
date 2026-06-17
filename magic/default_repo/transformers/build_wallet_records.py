from datetime import datetime, timezone
from pandas import DataFrame

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform_df(holders: DataFrame, resolved: DataFrame, *args, **kwargs) -> DataFrame:
    now = datetime.now(timezone.utc)
    if holders.empty:
        return DataFrame(columns=["wallet", "main_wallet", "is_tracked", "first_seen", "last_seen"])

    if resolved.empty:
        resolved = holders.copy()
        resolved["main_wallet"] = holders["wallet"]

    merged = holders.merge(resolved[["wallet", "main_wallet"]], on="wallet", how="left")
    merged["main_wallet"] = merged["main_wallet"].fillna(merged["wallet"])
    merged = merged.drop_duplicates(subset=["wallet"])
    merged["is_tracked"] = True
    merged["first_seen"] = now
    merged["last_seen"] = now
    merged["last_position_sync"] = None
    merged["last_trade_sync"] = None

    result = merged[["wallet", "main_wallet", "is_tracked", "first_seen", "last_seen",
                     "last_position_sync", "last_trade_sync"]]
    print(f"Built {len(result)} wallet records")
    return result


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
