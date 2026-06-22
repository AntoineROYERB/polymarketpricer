import concurrent.futures
import requests
import time
from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import load_condition_map

DATA_API = "https://data-api.polymarket.com"
POS_COLS = ["wallet", "market_id", "outcome_id", "side", "status",
            "avg_entry_price", "shares", "entry_time", "exit_time",
            "realized_pnl", "unrealized_pnl", "total_pnl"]


def fetch_positions_for_wallet(proxy: str) -> list[dict]:
    try:
        resp = requests.get(
            f"{DATA_API}/positions",
            params={"user": proxy, "limit": 500},
            timeout=(5, 30),
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return []


@data_loader
def load_data_from_api(tracked: DataFrame, *args, **kwargs) -> DataFrame:
    if tracked.empty:
        return DataFrame(columns=POS_COLS)

    print("Loading condition_id → market_id mapping...")
    cond_map = load_condition_map()
    print(f"  {len(cond_map)} markets mapped")

    proxy_wallets = tracked["main_wallet"].dropna().unique().tolist()
    n_wallets = len(proxy_wallets)
    print(f"Fetching positions for {n_wallets} proxy wallets")

    rows = []
    done = 0
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        fut_map = {executor.submit(fetch_positions_for_wallet, pw): pw for pw in proxy_wallets}
        for fut in concurrent.futures.as_completed(fut_map):
            done += 1
            positions = fut.result()
            pw = fut_map[fut]
            for p in positions:
                cond_id = p.get("conditionId")
                market_id = cond_map.get(cond_id) if cond_id else None
                if not market_id:
                    continue
                rows.append({
                    "wallet": pw,
                    "market_id": market_id,
                    "outcome_id": p.get("asset"),
                    "side": "BUY",
                    "status": "OPEN",
                    "avg_entry_price": p.get("avgPrice"),
                    "shares": p.get("size"),
                    "entry_time": None,
                    "exit_time": None,
                    "realized_pnl": p.get("realizedPnl"),
                    "unrealized_pnl": p.get("cashPnl"),
                    "total_pnl": p.get("cashPnl"),
                })
            if done % 200 == 0 or done == n_wallets:
                elapsed = time.time() - t0
                print(f"  {done}/{n_wallets} wallets, {len(rows)} positions, {elapsed:.0f}s")

    print(f"Total positions fetched: {len(rows)} in {time.time()-t0:.0f}s")
    return DataFrame(rows)


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
