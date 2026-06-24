import time

import requests
from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATA_API = "https://data-api.polymarket.com"
PAGE_SIZE = 500
MAX_TRADES = 10000
MIN_TRADE_AMOUNT_USD = 10.0
MIN_WALLET_VOLUME_USD = 100.0


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    addrs: set[str] = set()
    wallet_volume: dict[str, float] = {}
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
            if not pw:
                continue
            size = float(t.get("size", 0) or 0)
            price = float(t.get("price", 0) or 0)
            amount_usd = size * price
            if amount_usd < MIN_TRADE_AMOUNT_USD:
                continue
            addr = pw.lower()
            addrs.add(addr)
            wallet_volume[addr] = wallet_volume.get(addr, 0) + amount_usd
        offset += PAGE_SIZE
        page += 1
        print(f"  page {page}: {len(batch)} trades, {len(addrs)} wallets with trades >= ${MIN_TRADE_AMOUNT_USD}")
        if len(batch) < PAGE_SIZE:
            break
        time.sleep(0.1)
    filtered = {w for w in addrs if wallet_volume.get(w, 0) >= MIN_WALLET_VOLUME_USD}
    print(f"Total unique wallets found: {len(addrs)}, after ${MIN_WALLET_VOLUME_USD} volume filter: {len(filtered)}")
    return DataFrame({"wallet": sorted(filtered)})


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
