import concurrent.futures

import requests
from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

GAMMA_API = "https://gamma-api.polymarket.com"


def _resolve_single(addr: str) -> dict:
    try:
        resp = requests.get(f"{GAMMA_API}/users/{addr}", timeout=15)
        if resp.status_code == 200:
            user = resp.json()
            proxy = user.get("proxy_wallet") or user.get("proxyWallet")
            return {"wallet": addr, "main_wallet": proxy or addr}
    except requests.RequestException:
        pass
    return {"wallet": addr, "main_wallet": addr}


@data_loader
def load_data_from_api(holders: DataFrame, *args, **kwargs) -> DataFrame:
    if holders.empty:
        return DataFrame(columns=["wallet", "main_wallet"])

    addrs = holders["wallet"].tolist()
    print(f"Resolving proxy wallets for {len(addrs)} addresses")

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        fut_map = {executor.submit(_resolve_single, addr): addr for addr in addrs}
        for i, fut in enumerate(concurrent.futures.as_completed(fut_map), 1):
            addr = fut_map[fut]
            try:
                rows.append(fut.result())
            except Exception:
                rows.append({"wallet": addr, "main_wallet": addr})
            if i % 100 == 0 or i == len(addrs):
                print(f"  resolved {i}/{len(addrs)} wallets")

    print(f"Proxy resolution complete — {len(rows)} records")
    return DataFrame(rows)


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
