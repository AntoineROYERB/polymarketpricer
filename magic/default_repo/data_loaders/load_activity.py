import concurrent.futures
import queue
import time
from datetime import datetime, timedelta, timezone

import requests
from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import load_condition_map

DATA_API = "https://data-api.polymarket.com"
PAGE_SIZE = 500
MAX_CONCURRENT = 10
MAX_QUEUED_EVENTS = 20000

WALLET_AGG_COLS = [
    "wallet",
    "total_bought", "total_sold", "total_redeemed",
    "total_merged", "total_split", "total_rebates",
    "num_activity_events",
    "category_breakdown",
]


def classify_activity_type(event: dict) -> tuple[str, str | None]:
    event_type = event.get("type", "").upper()
    if event_type == "TRADE":
        side = event.get("side", "").upper()
        if side in ("BUY", "SELL"):
            return ("TRADE", side)
        return ("TRADE", None)
    elif event_type in ("REDEEM", "MERGE", "SPLIT", "REBATE"):
        return (event_type, None)
    return ("UNKNOWN", None)


def _init_wallet_agg() -> dict:
    return {
        "total_bought": 0.0,
        "total_sold": 0.0,
        "total_redeemed": 0.0,
        "total_merged": 0.0,
        "total_split": 0.0,
        "total_rebates": 0.0,
        "num_activity_events": 0,
        "categories": set(),
        # Per-category aggregates for computing accurate category PnL
        "cat_agg": {},
    }


def _init_cat_agg() -> dict:
    return {
        "total_bought": 0.0,
        "total_sold": 0.0,
        "total_redeemed": 0.0,
        "total_merged": 0.0,
        "total_split": 0.0,
        "total_rebates": 0.0,
        "num_events": 0,
    }


def _accumulate_wallet(agg: dict, activity_type: str, side: str | None, amount: float) -> None:
    agg["num_activity_events"] += 1
    if activity_type == "TRADE" and side == "BUY":
        agg["total_bought"] += amount
    elif activity_type == "TRADE" and side == "SELL":
        agg["total_sold"] += amount
    elif activity_type == "REDEEM":
        agg["total_redeemed"] += amount
    elif activity_type == "MERGE":
        agg["total_merged"] += amount
    elif activity_type == "SPLIT":
        agg["total_split"] += amount
    elif activity_type == "REBATE":
        agg["total_rebates"] += amount


def _accumulate_category(cat_agg: dict, activity_type: str, side: str | None, amount: float) -> None:
    cat_agg["num_events"] += 1
    if activity_type == "TRADE" and side == "BUY":
        cat_agg["total_bought"] += amount
    elif activity_type == "TRADE" and side == "SELL":
        cat_agg["total_sold"] += amount
    elif activity_type == "REDEEM":
        cat_agg["total_redeemed"] += amount
    elif activity_type == "MERGE":
        cat_agg["total_merged"] += amount
    elif activity_type == "SPLIT":
        cat_agg["total_split"] += amount
    elif activity_type == "REBATE":
        cat_agg["total_rebates"] += amount


def _accumulate_event(agg: dict, activity_type: str, side: str | None, amount: float,
                      category: str | None) -> None:
    _accumulate_wallet(agg, activity_type, side, amount)
    if category:
        agg["categories"].add(category)
        cat_agg = agg["cat_agg"].setdefault(category, _init_cat_agg())
        _accumulate_category(cat_agg, activity_type, side, amount)


def _build_category_breakdown(agg: dict) -> dict | None:
    if not agg["cat_agg"]:
        return None
    result = {}
    for cat, ca in agg["cat_agg"].items():
        realized = (
            ca["total_sold"] + ca["total_redeemed"]
            + ca["total_merged"] + ca["total_rebates"]
            - ca["total_bought"] - ca["total_split"]
        )
        result[cat] = {
            "total_realized_pnl": round(realized, 2),
            "total_bought": round(ca["total_bought"], 2),
            "total_sold": round(ca["total_sold"], 2),
            "total_redeemed": round(ca["total_redeemed"], 2),
            "num_events": ca["num_events"],
        }
    return result


def fetch_activity_for_wallet(proxy: str, since_ts: float,
                              event_queue: queue.Queue) -> None:
    """Fetch all activity pages for one wallet, enqueueing events individually.

    Each event is pushed as ("event", proxy, event_dict).
    A final ("done", proxy, None) signals completion.
    """
    session = requests.Session()
    try:
        end_cursor = None
        while True:
            params = {"user": proxy, "limit": PAGE_SIZE}
            if end_cursor:
                params["end"] = end_cursor
            resp = session.get(
                f"{DATA_API}/activity",
                params=params,
                timeout=(5, 30),
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            for ev in batch:
                try:
                    ev_ts = ev.get("timestamp")
                    if ev_ts is None or int(ev_ts) < since_ts:
                        continue
                    event_queue.put(("event", proxy, ev))
                except (ValueError, TypeError):
                    continue
            if len(batch) < PAGE_SIZE:
                break
            last_ts = batch[-1].get("timestamp")
            if last_ts:
                try:
                    if int(last_ts) < since_ts:
                        break
                    end_cursor = str(int(last_ts) - 1)
                except (ValueError, TypeError):
                    break
            else:
                break
    except requests.RequestException:
        pass
    finally:
        session.close()
        event_queue.put(("done", proxy, None))


def _process_event(ev: dict, proxy: str, cond_map: dict, cat_map: dict,
                   wallet_data: dict) -> None:
    cond_id = ev.get("conditionId")
    market_id = cond_map.get(cond_id) if cond_id else None
    if not market_id:
        return
    activity_type, side = classify_activity_type(ev)
    if activity_type == "UNKNOWN":
        return
    amount = float(ev.get("size", 0) or 0) * float(ev.get("price", 0) or 0)
    category = cat_map.get(market_id)
    agg = wallet_data.get(proxy)
    if agg is None:
        agg = _init_wallet_agg()
        wallet_data[proxy] = agg
    _accumulate_event(agg, activity_type, side, amount, category)


@data_loader
def load_data_from_api(tracked: DataFrame, *args, **kwargs) -> DataFrame:
    if tracked.empty:
        return DataFrame(columns=WALLET_AGG_COLS)

    print("Loading condition_id -> market_id and category maps...")
    cond_map = load_condition_map()

    engine = create_engine("postgresql://app:devpassword@postgres:5432/polymarket")
    market_cat = DataFrame(engine.execute(
        text("SELECT id AS market_id, mapped_category AS category FROM markets "
             "WHERE mapped_category IS NOT NULL")
    ).fetchall())
    cat_map = dict(zip(market_cat["market_id"], market_cat["category"]))
    engine.dispose()
    print(f"  {len(cond_map)} markets mapped, {len(cat_map)} with categories")

    proxy_wallets = tracked["main_wallet"].dropna().unique().tolist()
    n_wallets = len(proxy_wallets)
    print(f"Fetching activity for {n_wallets} wallets")

    since_ts = (datetime.now(timezone.utc) - timedelta(days=365)).timestamp()
    wallet_data: dict[str, dict] = {}
    event_queue: queue.Queue = queue.Queue(maxsize=MAX_QUEUED_EVENTS)
    done_wallets: set[str] = set()
    t0 = time.time()
    last_report = 0

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT)

    # Submit all wallets at once — each worker streams events through the queue.
    # Futures return None; data never accumulates in future results.
    fut_map = {
        executor.submit(fetch_activity_for_wallet, pw, since_ts, event_queue): pw
        for pw in proxy_wallets
    }

    try:
        while len(done_wallets) < n_wallets:
            kind, proxy, ev = event_queue.get()
            if kind == "done":
                done_wallets.add(proxy)
                d = len(done_wallets)
                if d - last_report >= 200 or d == n_wallets:
                    elapsed = time.time() - t0
                    print(f"  {d}/{n_wallets} wallets, {len(wallet_data)} with activity, {elapsed:.0f}s")
                    last_report = d
            elif kind == "event":
                _process_event(ev, proxy, cond_map, cat_map, wallet_data)

        # Surface any worker errors
        for fut in concurrent.futures.as_completed(fut_map):
            try:
                fut.result()
            except Exception as e:
                pw = fut_map[fut]
                print(f"  WARNING: {pw} failed: {e}")
    finally:
        executor.shutdown(wait=True)

    agg_rows = []
    for wallet, agg in wallet_data.items():
        agg_rows.append({
            "wallet": wallet,
            "total_bought": round(agg["total_bought"], 2),
            "total_sold": round(agg["total_sold"], 2),
            "total_redeemed": round(agg["total_redeemed"], 2),
            "total_merged": round(agg["total_merged"], 2),
            "total_split": round(agg["total_split"], 2),
            "total_rebates": round(agg["total_rebates"], 2),
            "num_activity_events": agg["num_activity_events"],
            "category_breakdown": _build_category_breakdown(agg),
        })

    activity_df = DataFrame(agg_rows, columns=WALLET_AGG_COLS) if agg_rows else DataFrame(columns=WALLET_AGG_COLS)
    print(f"Total wallets with activity: {len(activity_df)}")
    return activity_df


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
