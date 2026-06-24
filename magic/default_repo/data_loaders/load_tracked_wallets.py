from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"

# Max wallets to process per pipeline run. Prevents the pipeline from timing out
# when there are many tracked wallets. Increase if your SLA supports more.
_DEFAULT_LIMIT = 50


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    engine = create_engine(DATABASE_URL)
    df = read_sql(
        text(f"SELECT wallet, main_wallet FROM wallets WHERE is_tracked = true LIMIT {_DEFAULT_LIMIT}"),
        engine,
    )
    engine.dispose()
    print(f"Loaded {len(df)} tracked wallets")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
