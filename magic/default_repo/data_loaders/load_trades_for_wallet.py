import concurrent.futures
import requests
import time
from datetime import datetime, timezone
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import load_condition_map

DATA_API = "https://data-api.polymarket.com"
PAGE_SIZE = 500
BATCH_WALLETS = 200
INSERT_BATCH = 1000

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"

INSERT_SQL = text("""
    INSERT INTO trades (id, wallet, market_id, outcome_id, side, type,
                        price, shares, amount_usd, fee_usd, timestamp, tx_hash)
    VALUES (:id, :wallet, :market_id, :outcome_id, :side, :type,
            :price, :shares, :amount_usd, :fee_usd, :timestamp, :tx_hash)
    ON CONFLICT (id) DO NOTHING
""")


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


def export_rows(conn, rows: list[dict]):
    for i in range(0, len(rows), INSERT_BATCH):
        conn.execute(INSERT_SQL, rows[i:i + INSERT_BATCH])


@data_loader
def load_data_from_api(tracked: DataFrame, *args, **kwargs) -> DataFrame:
    if tracked.empty:
        return DataFrame()

    print("Loading condition_id -> market_id mapping...")
    cond_map = load_condition_map()
    print(f"  {len(cond_map)} markets mapped")

    proxy_wallets = tracked["main_wallet"].dropna().unique().tolist()
    n_wallets = len(proxy_wallets)
    print(f"Fetching trades for {n_wallets} wallets")

    engine = create_engine(DATABASE_URL)
    total_trades = 0
    done = 0
    t0 = time.time()

    for chunk_start in range(0, n_wallets, BATCH_WALLETS):
        chunk = proxy_wallets[chunk_start:chunk_start + BATCH_WALLETS]
        chunk_rows = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            fut_map = {
                executor.submit(fetch_trades_for_wallet, pw): pw
                for pw in chunk
            }
            for fut in concurrent.futures.as_completed(fut_map):
                done += 1
                trades = fut.result()
                pw = fut_map[fut]
                rows = map_fields(trades, pw, cond_map)
                chunk_rows.extend(rows)

        if chunk_rows:
            with engine.begin() as conn:
                export_rows(conn, chunk_rows)
            total_trades += len(chunk_rows)

        elapsed = time.time() - t0
        print(f"  {done}/{n_wallets} wallets, {total_trades} trades, {elapsed:.0f}s")

    engine.dispose()
    print(f"Total trades exported: {total_trades} in {time.time()-t0:.0f}s")
    return DataFrame()


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
