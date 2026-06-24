#!/usr/bin/env python3
"""One-shot backfill: compute PnL for all wallets from /activity and write to wallet_pnl_snapshots.

Usage:
    python scripts/backfill_pnl.py [--wallet 0x...]
"""

import argparse
import sys
sys.path.insert(0, ".")

from datetime import date, datetime, timedelta, timezone
from pandas import DataFrame
from sqlalchemy import create_engine, text
import requests

from magic.default_repo.data_loaders.load_activity import (
    classify_activity_type,
)
from magic.default_repo.utils.db_helpers import load_condition_map

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


DATA_API = "https://data-api.polymarket.com"
PAGE_SIZE = 500


def fetch_activity_sync(wallet: str, since_ts: float) -> list[dict]:
    """Synchronous version of the activity fetch for backfill purposes.

    Fetches all pages using cursor-based pagination. Returns a flat list
    of event dicts (the same shape the pipelined loader uses internally).
    """
    all_events: list[dict] = []
    end_cursor: str | None = None
    while True:
        params: dict = {"user": wallet, "limit": PAGE_SIZE}
        if end_cursor:
            params["end"] = end_cursor
        try:
            resp = requests.get(
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
                    ts = ev.get("timestamp")
                    if ts is not None and int(ts) >= since_ts:
                        all_events.append(ev)
                except (ValueError, TypeError):
                    continue
            if len(batch) < PAGE_SIZE:
                break
            last_ts = batch[-1].get("timestamp")
            if last_ts:
                end_cursor = str(int(last_ts) - 1)
            else:
                break
        except requests.RequestException:
            break
    return all_events


def backfill_wallet(wallet: str, since_ts: float,
                    cond_map: dict, cat_map: dict, engine) -> None:
    events = fetch_activity_sync(wallet, since_ts)
    if not events:
        print(f"  {wallet}: no activity")
        return

    rows = []
    for ev in events:
        cond_id = ev.get("conditionId")
        market_id = cond_map.get(cond_id) if cond_id else None
        if not market_id:
            continue
        activity_type, side = classify_activity_type(ev)
        if activity_type == "UNKNOWN":
            continue
        amount = float(ev.get("size", 0) or 0) * float(ev.get("price", 0) or 0)
        rows.append({
            "wallet": wallet,
            "market_id": market_id,
            "category": cat_map.get(market_id),
            "activity_type": activity_type,
            "side": side,
            "amount_usd": amount,
        })

    if not rows:
        return

    df = DataFrame(rows)
    buys = df[(df["activity_type"] == "TRADE") & (df["side"] == "BUY")]["amount_usd"].sum()
    sells = df[(df["activity_type"] == "TRADE") & (df["side"] == "SELL")]["amount_usd"].sum()
    redeems = df[df["activity_type"] == "REDEEM"]["amount_usd"].sum()
    merges = df[df["activity_type"] == "MERGE"]["amount_usd"].sum()
    splits = df[df["activity_type"] == "SPLIT"]["amount_usd"].sum()
    rebates = df[df["activity_type"] == "REBATE"]["amount_usd"].sum()

    realized_pnl = sells + redeems + merges + rebates - buys - splits

    result = engine.execute(
        text("SELECT COALESCE(SUM(unrealized_pnl), 0) FROM positions "
             "WHERE wallet = :wallet AND status = 'OPEN'"),
        {"wallet": wallet},
    ).scalar()
    open_value = float(result or 0)

    total_pnl = realized_pnl + open_value

    engine.execute(
        text("""
            INSERT INTO wallet_pnl_snapshots (
                wallet, snapshot_date, total_pnl, total_realized_pnl,
                total_unrealized_pnl, total_bought, total_sold,
                total_redeemed, total_merged, total_split, total_rebates,
                num_activity_events, open_position_value
            ) VALUES (
                :wallet, :today, :total_pnl, :realized_pnl,
                :unrealized_pnl, :bought, :sold,
                :redeemed, :merged, :split, :rebates,
                :events, :open_value
            )
            ON CONFLICT (wallet, snapshot_date) DO UPDATE SET
                total_pnl = EXCLUDED.total_pnl,
                total_realized_pnl = EXCLUDED.total_realized_pnl,
                total_unrealized_pnl = EXCLUDED.total_unrealized_pnl,
                computed_at = NOW()
        """),
        {
            "wallet": wallet,
            "today": date.today(),
            "total_pnl": round(total_pnl, 2),
            "realized_pnl": round(realized_pnl, 2),
            "unrealized_pnl": round(open_value, 2),
            "bought": round(buys, 2),
            "sold": round(sells, 2),
            "redeemed": round(redeems, 2),
            "merged": round(merges, 2),
            "split": round(splits, 2),
            "rebates": round(rebates, 2),
            "events": len(rows),
            "open_value": round(open_value, 2),
        },
    )
    print(f"  {wallet}: PnL={total_pnl:.2f}, events={len(rows)}")


def main():
    parser = argparse.ArgumentParser(description="Backfill PnL from /activity")
    parser.add_argument("--wallet", help="Specific wallet to backfill (default: all)")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    cond_map = load_condition_map()
    cat_map = dict(engine.execute(
        text("SELECT id, mapped_category FROM markets WHERE mapped_category IS NOT NULL")
    ).fetchall())

    if args.wallet:
        wallets = [args.wallet]
    else:
        wallets = [r[0] for r in engine.execute(
            text("SELECT DISTINCT wallet FROM trades")
        ).fetchall()]

    print(f"Backfilling PnL for {len(wallets)} wallets...")
    since_ts = (datetime.now(timezone.utc) - timedelta(days=365)).timestamp()
    for i, w in enumerate(wallets, 1):
        backfill_wallet(w, since_ts, cond_map, cat_map, engine)
        if i % 50 == 0:
            print(f"  progress: {i}/{len(wallets)}")

    engine.dispose()
    print("Backfill complete")


if __name__ == "__main__":
    main()
