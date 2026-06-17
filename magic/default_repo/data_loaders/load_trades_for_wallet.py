import concurrent.futures
import requests
import time
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from pandas import DataFrame

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATA_API = "https://data-api.polymarket.com"
DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"
PAGE_SIZE = 500
TRADE_COLS = ["id", "wallet", "market_id", "outcome_id", "side",
              "type", "price", "shares", "amount_usd", "fee_usd",
              "timestamp", "tx_hash"]


def load_condition_map() -> dict:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, condition_id FROM markets WHERE condition_id IS NOT NULL")
        )
        mapping = {row.condition_id: row.id for row in rows}
    engine.dispose()
    return mapping


def fetch_trades_for_wallet(proxy: str) -> list[dict]:
    try:
        all_trades = []
        offset = 0
        while True:
            resp = requests.get(
                f"{DATA_API}/trades",
                params={"user": proxy, "limit": PAGE_SIZE, "offset": offset},
                timeout=(5, 30),
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            all_trades.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
            time.sleep(0.05)
        return all_trades
    except requests.RequestException:
        return []


def map_fields(trades: list[dict], wallet: str, cond_map: dict) -> list[dict]:
    rows = []
    for t in trades:
        cond_id = t.get("conditionId")
        market_id = cond_map.get(cond_id) if cond_id else None
        if not market_id:
            continue
        tx_hash = t.get("transactionHash") or t.get("txHash")
        asset = t.get("asset")
        ts = t.get("timestamp")
        rows.append({
            "id": f"{tx_hash}-{asset}" if tx_hash and asset else (tx_hash or asset),
            "wallet": wallet,
            "market_id": market_id,
            "outcome_id": asset,
            "side": t.get("side", "BUY"),
            "type": t.get("type", "MARKET"),
            "price": t.get("price"),
            "shares": t.get("size"),
            "amount_usd": float(t.get("size", 0)) * float(t.get("price", 0)),
            "fee_usd": t.get("fee"),
            "timestamp": datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else None,
            "tx_hash": tx_hash,
        })
    return rows


@data_loader
def load_data_from_api(tracked: DataFrame, *args, **kwargs) -> DataFrame:
    if tracked.empty:
        return DataFrame(columns=TRADE_COLS)

    print("Loading condition_id -> market_id mapping...")
    cond_map = load_condition_map()
    print(f"  {len(cond_map)} markets mapped")

    proxy_wallets = tracked["main_wallet"].dropna().unique().tolist()
    n_wallets = len(proxy_wallets)
    print(f"Fetching trades for {n_wallets} wallets")

    all_rows = []
    done = 0
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        fut_map = {
            executor.submit(fetch_trades_for_wallet, pw): pw
            for pw in proxy_wallets
        }
        for fut in concurrent.futures.as_completed(fut_map):
            done += 1
            trades = fut.result()
            pw = fut_map[fut]
            rows = map_fields(trades, pw, cond_map)
            all_rows.extend(rows)
            if done % 200 == 0 or done == n_wallets:
                elapsed = time.time() - t0
                print(f"  {done}/{n_wallets} wallets, {len(all_rows)} trades, {elapsed:.0f}s")

    print(f"Total trades fetched: {len(all_rows)} in {time.time()-t0:.0f}s")
    return DataFrame(all_rows)


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
