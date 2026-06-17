from pandas import DataFrame

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform_df(df: DataFrame, *args, **kwargs) -> DataFrame:
    if df.empty:
        return df

    before = len(df)
    df = df.drop_duplicates(subset=["id"], keep="first")
    after = len(df)
    print(f"De-duplicated trades: {before} → {after} ({before - after} duplicates removed)")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
