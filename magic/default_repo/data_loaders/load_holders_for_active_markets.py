import requests
import time
from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATA_API = "https://data-api.polymarket.com"
PAGE_SIZE = 500
MAX_TRADES = 10000


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    addrs: set[str] = set()
    offset = 0
    page = 0
    while offset < MAX_TRADES:
        try:
            resp = requests.get(
                f"{DATA_API}/trades",
                params={"limit": PAGE_SIZE, "offset": offset},
                timeout=30,
            )
            if resp.status_code != 200:
                print(f"  page {page}: status {resp.status_code}, stopping")
                break
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  request failed: {e}")
            break
        batch = resp.json()
        if not batch:
            break
        for t in batch:
            pw = t.get("proxyWallet")
            if pw:
                addrs.add(pw.lower())
        offset += PAGE_SIZE
        page += 1
        print(f"  page {page}: {len(batch)} trades, {len(addrs)} unique wallets")
        if len(batch) < PAGE_SIZE:
            break
        time.sleep(0.1)
    print(f"Total unique wallets found: {len(addrs)}")
    return DataFrame({"wallet": sorted(addrs)})


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
