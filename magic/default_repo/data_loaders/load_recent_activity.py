from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    engine = create_engine(DATABASE_URL)
    df = read_sql(
        text("""
            SELECT DISTINCT wallet FROM trades
            WHERE timestamp >= CURRENT_DATE - INTERVAL '1 day'
        """),
        engine,
    )
    engine.dispose()
    print(f"Active wallets with recent trades: {len(df)}")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
