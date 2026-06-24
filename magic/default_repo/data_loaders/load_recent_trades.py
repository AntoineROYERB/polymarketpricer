from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_loader
def load_data_from_api(*args, **kwargs) -> DataFrame:
    engine = create_engine(DATABASE_URL)
    df = read_sql(
        text("""
            SELECT wallet, market_id, side, price, shares, amount_usd, timestamp
            FROM trades
            WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
            ORDER BY timestamp DESC
        """),
        engine,
    )
    engine.dispose()
    print(f"Loaded {len(df)} recent trades")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
