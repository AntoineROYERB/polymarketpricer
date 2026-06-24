from datetime import date

from pandas import DataFrame, notna

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

SNAPSHOT_COLS = [
    "wallet", "snapshot_date",
    "total_pnl", "total_realized_pnl", "total_unrealized_pnl",
    "total_bought", "total_sold", "total_redeemed",
    "total_merged", "total_split", "total_rebates",
    "num_activity_events", "open_position_value",
    "category_breakdown",
]


def _default_wallet_entry(wallet: str, today: date) -> dict:
    return {
        "wallet": wallet,
        "snapshot_date": today,
        "total_realized_pnl": 0,
        "total_bought": 0,
        "total_sold": 0,
        "total_redeemed": 0,
        "total_merged": 0,
        "total_split": 0,
        "total_rebates": 0,
        "num_activity_events": 0,
        "total_unrealized_pnl": 0,
        "open_position_value": 0,
        "total_pnl": None,
    }


def compute_pnl(activity: DataFrame, open_positions: DataFrame) -> DataFrame:
    today = date.today()

    if activity.empty and open_positions.empty:
        print("No activity or open positions -- returning empty DataFrame")
        return DataFrame(columns=SNAPSHOT_COLS)

    wallet_pnl: dict[str, dict] = {}

    if not activity.empty:
        for _, row in activity.iterrows():
            wallet = row["wallet"]
            bought = float(row["total_bought"]) if notna(row["total_bought"]) else 0
            sold = float(row["total_sold"]) if notna(row["total_sold"]) else 0
            redeemed = float(row["total_redeemed"]) if notna(row["total_redeemed"]) else 0
            merged = float(row["total_merged"]) if notna(row["total_merged"]) else 0
            split = float(row["total_split"]) if notna(row["total_split"]) else 0
            rebates = float(row["total_rebates"]) if notna(row["total_rebates"]) else 0

            realized = sold + redeemed + merged + rebates - bought - split

            entry = _default_wallet_entry(wallet, today)
            entry.update({
                "total_realized_pnl": round(realized, 2),
                "total_bought": round(bought, 2),
                "total_sold": round(sold, 2),
                "total_redeemed": round(redeemed, 2),
                "total_merged": round(merged, 2),
                "total_split": round(split, 2),
                "total_rebates": round(rebates, 2),
                "num_activity_events": int(row["num_activity_events"]) if notna(row["num_activity_events"]) else 0,
            })
            wallet_pnl[wallet] = entry

    # Accumulate unrealized PnL per wallet (a wallet may have multiple open positions)
    open_value_by_wallet: dict[str, float] = {}
    if not open_positions.empty:
        for _, pos in open_positions.iterrows():
            w = pos["wallet"]
            raw = pos.get("unrealized_pnl", 0)
            val = float(raw) if notna(raw) else 0.0
            open_value_by_wallet[w] = open_value_by_wallet.get(w, 0.0) + val

    for w, val in open_value_by_wallet.items():
        if w not in wallet_pnl:
            wallet_pnl[w] = _default_wallet_entry(w, today)
        wallet_pnl[w]["total_unrealized_pnl"] = round(val, 2)
        wallet_pnl[w]["open_position_value"] = round(val, 2)
        realized = wallet_pnl[w]["total_realized_pnl"] or 0
        wallet_pnl[w]["total_pnl"] = round(realized + val, 2)

    for w in wallet_pnl:
        if wallet_pnl[w]["total_pnl"] is None:
            wallet_pnl[w]["total_pnl"] = wallet_pnl[w]["total_realized_pnl"]

    # Category breakdown — pass through pre-computed values from load_activity
    if "category_breakdown" in activity.columns:
        for _, row in activity.iterrows():
            wallet = row["wallet"]
            cb = row.get("category_breakdown")
            if cb is not None and wallet in wallet_pnl:
                wallet_pnl[wallet]["category_breakdown"] = cb
    for w in wallet_pnl:
        wallet_pnl[w].setdefault("category_breakdown", None)

    rows = list(wallet_pnl.values())
    print(f"Computed PnL for {len(rows)} wallets")
    return DataFrame(rows) if rows else DataFrame(columns=SNAPSHOT_COLS)


@transformer
def transform_df(activity: DataFrame, open_positions: DataFrame, *args, **kwargs) -> DataFrame:
    return compute_pnl(activity, open_positions)


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert "total_pnl" in df.columns, "Missing total_pnl"
        for _, row in df.iterrows():
            if notna(row["total_unrealized_pnl"]):
                expected = round((row["total_realized_pnl"] or 0) + row["total_unrealized_pnl"], 2)
                assert abs((row["total_pnl"] or 0) - expected) < 0.01, (
                    f"total_pnl mismatch for {row['wallet']}: "
                    f"{row['total_pnl']} != {expected}"
                )
