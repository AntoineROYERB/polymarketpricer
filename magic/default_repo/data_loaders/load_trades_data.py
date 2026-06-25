from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL


@data_loader
def load_data_from_api(active_wallets: DataFrame, *args, **kwargs) -> DataFrame:
    if active_wallets.empty:
        return DataFrame()

    wallets_list = active_wallets["wallet"].tolist()
    engine = create_engine(DATABASE_URL)
    df = read_sql(
        text("""
            SELECT wallet, market_id, amount_usd, price, shares, fee_usd, side, timestamp
            FROM trades
            WHERE wallet = ANY(:wallets)
              AND timestamp >= CURRENT_DATE - INTERVAL '90 days'
        """),
        engine,
        params={"wallets": wallets_list},
    )
    engine.dispose()
    print(f"Loaded {len(df)} trade rows for recent wallets")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
