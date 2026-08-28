import os
import time

import requests
from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATA_API = "https://data-api.polymarket.com"
PAGE_SIZE = 500
TARGET_WALLET_COUNT = int(os.environ.get("TARGET_WALLET_COUNT", 1000))


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    addrs: set[str] = set()
    offset = 0
    page = 0
    while len(addrs) < TARGET_WALLET_COUNT and offset < 10000:
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
            addr = pw.lower()
            addrs.add(addr)
        offset += PAGE_SIZE
        page += 1
        print(f"  page {page}: {len(batch)} trades, {len(addrs)} unique wallets (target: {TARGET_WALLET_COUNT})")
        if len(batch) < PAGE_SIZE:
            break
        time.sleep(0.1)
    print(f"Total unique wallets collected: {len(addrs)}")
    return DataFrame({"wallet": sorted(addrs)})


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
    assert not df.empty, 'No wallets discovered'
