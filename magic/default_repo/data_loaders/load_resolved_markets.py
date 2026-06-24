from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.market_fetcher import build_market_rows, fetch_markets


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    markets = fetch_markets(closed=True)
    print(f"Fetched {len(markets)} resolved markets total")
    return DataFrame(build_market_rows(markets))


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
