from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from utils.market_fetcher import fetch_markets, build_market_rows


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    markets = fetch_markets(closed=False)
    print(f"Fetched {len(markets)} active markets total")
    return DataFrame(build_market_rows(markets))


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
    assert not df.empty, 'No active markets loaded'
