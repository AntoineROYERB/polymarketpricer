import requests
import time
from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

GAMMA_API = "https://gamma-api.polymarket.com"
RATE_LIMIT_SPACING = 0.05


@data_loader
def load_data_from_api(holders: DataFrame, *args, **kwargs) -> DataFrame:
    if holders.empty:
        return DataFrame(columns=["wallet", "main_wallet"])

    addrs = holders["wallet"].tolist()
    print(f"Resolving proxy wallets for {len(addrs)} addresses")
    rows = []
    for i, addr in enumerate(addrs, 1):
        try:
            resp = requests.get(f"{GAMMA_API}/users/{addr}", timeout=15)
            if resp.status_code == 200:
                user = resp.json()
                proxy = user.get("proxy_wallet") or user.get("proxyWallet")
                rows.append({"wallet": addr, "main_wallet": proxy or addr})
            else:
                rows.append({"wallet": addr, "main_wallet": addr})
        except requests.RequestException:
            rows.append({"wallet": addr, "main_wallet": addr})
        if i % 100 == 0 or i == len(addrs):
            print(f"  resolved {i}/{len(addrs)} wallets")
        time.sleep(RATE_LIMIT_SPACING)

    print(f"Proxy resolution complete — {len(rows)} records")
    return DataFrame(rows)


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
