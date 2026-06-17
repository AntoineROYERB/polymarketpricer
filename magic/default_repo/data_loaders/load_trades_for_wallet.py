import requests
import time
from datetime import datetime, timezone
from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

GAMMA_API = "https://gamma-api.polymarket.com"
RATE_LIMIT_SPACING = 0.05


def fetch_trades(proxy_wallet: str, backfill: bool = False, oldest_known: str = None) -> list[dict]:
    all_trades = []
    cursor = None
    while True:
        params = {"user": proxy_wallet, "limit": 500}
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(
            f"{GAMMA_API}/trades",
            params=params,
            timeout=30,
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break

        if isinstance(data, dict):
            trades = data.get("data", [])
            cursor = data.get("cursor") or data.get("next_cursor")
        elif isinstance(data, list):
            trades = data
            cursor = None
        else:
            break

        if not trades:
            break

        if not backfill:
            cutoff = None
            for t in trades:
                ts = t.get("timestamp") or t.get("created_at")
                if ts and oldest_known and ts < oldest_known:
                    cutoff = ts
                    break
            if cutoff:
                all_trades.extend([t for t in trades if (t.get("timestamp") or t.get("created_at")) >= cutoff])
                break

        all_trades.extend(trades)
        if not cursor:
            break
        time.sleep(RATE_LIMIT_SPACING)

    return all_trades


@data_loader
def load_data_from_api(tracked: DataFrame, *args, **kwargs) -> DataFrame:
    if tracked.empty:
        return DataFrame(columns=["id", "wallet", "market_id", "outcome_id", "side",
                                   "type", "price", "shares", "amount_usd", "fee_usd",
                                   "timestamp", "tx_hash"])

    backfill = kwargs.get("backfill", False)
    rows = []
    proxy_wallets = tracked["main_wallet"].dropna().unique().tolist()
    n = len(proxy_wallets)
    print(f"Fetching trades for {n} wallets (backfill={backfill})")

    for i, proxy in enumerate(proxy_wallets, 1):
        trades = fetch_trades(proxy, backfill=backfill, oldest_known=None)
        for t in trades:
            rows.append({
                "id": t.get("id") or t.get("transaction_id"),
                "wallet": proxy,
                "market_id": t.get("market") or t.get("market_id"),
                "outcome_id": t.get("outcome_id"),
                "side": t.get("side", "BUY"),
                "type": t.get("type", "MARKET"),
                "price": t.get("price"),
                "shares": t.get("shares") or t.get("size"),
                "amount_usd": t.get("amount_usd") or t.get("value"),
                "fee_usd": t.get("fee_usd") or t.get("fee"),
                "timestamp": t.get("timestamp") or t.get("created_at"),
                "tx_hash": t.get("tx_hash") or t.get("transaction_hash"),
            })
        if i % 10 == 0 or i == n:
            print(f"  wallet {i}/{n}, {len(rows)} trades collected so far")
        time.sleep(RATE_LIMIT_SPACING)

    print(f"Total trades fetched: {len(rows)}")
    return DataFrame(rows)


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
