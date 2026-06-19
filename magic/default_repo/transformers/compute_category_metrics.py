import math
from datetime import date, timedelta

from pandas import DataFrame, to_numeric, NaT, concat

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from transformers.compute_wallet_metrics import safe_div, MIN_RESOLVED_TRADES

MIN_CATEGORY_TRADES = 30


def compute_category_metrics_for_wallet(
    wallet: str,
    category: str,
    trades: DataFrame,
    positions: DataFrame,
) -> dict | None:
    today = date.today()

    total_realized_pnl = 0.0
    total_unrealized_pnl = 0.0
    total_cost_basis = 0.0
    total_volume = 0.0
    num_trades = 0
    resolved_wins = 0
    resolved_total = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_holding_seconds = 0.0
    holding_count = 0

    if not trades.empty:
        wt = trades.copy()
        wt["amount_usd"] = to_numeric(wt["amount_usd"], errors="coerce").fillna(0)
        wt["price"] = to_numeric(wt["price"], errors="coerce").fillna(0)
        wt["shares"] = to_numeric(wt["shares"], errors="coerce").fillna(0)
        wt["fee_usd"] = to_numeric(wt["fee_usd"], errors="coerce").fillna(0)

        num_trades = len(wt)
        total_volume = float(wt["amount_usd"].abs().sum())

        buys = wt[wt["side"] == "BUY"]
        sells = wt[wt["side"] == "SELL"]
        total_cost_basis = float(
            (buys["price"] * buys["shares"]).sum()
            + (sells["price"] * sells["shares"]).abs().sum()
        )

    if not positions.empty:
        wp = positions.copy()
        wp["realized_pnl"] = to_numeric(wp["realized_pnl"], errors="coerce").fillna(0)
        wp["unrealized_pnl"] = to_numeric(wp["unrealized_pnl"], errors="coerce").fillna(0)
        wp["total_pnl"] = to_numeric(wp["total_pnl"], errors="coerce").fillna(0)

        total_realized_pnl = float(wp["realized_pnl"].sum())
        total_unrealized_pnl = float(wp["unrealized_pnl"].sum())

        resolved = wp[wp["status"].isin(["RESOLVED", "CLOSED"])]
        resolved_total = len(resolved)
        resolved_wins = int((resolved["realized_pnl"] > 0).sum())

        for _, p in resolved.iterrows():
            pnl = float(p["realized_pnl"])
            if pnl > 0:
                gross_profit += pnl
            elif pnl < 0:
                gross_loss += abs(pnl)

        for _, p in resolved.iterrows():
            et = p.get("entry_time")
            xt = p.get("exit_time")
            if et and xt and et is not NaT and xt is not NaT:
                delta = (xt - et).total_seconds()
                if delta > 0:
                    total_holding_seconds += delta
                    holding_count += 1

    total_pnl = total_realized_pnl + total_unrealized_pnl

    roi = safe_div(total_pnl, total_cost_basis) * 100 if total_cost_basis else None
    if roi is not None:
        roi = round(roi, 6)

    win_rate = safe_div(resolved_wins, resolved_total)
    if win_rate is not None:
        win_rate = round(win_rate, 6)

    profit_factor = safe_div(gross_profit, gross_loss) if gross_loss > 0 else None
    if profit_factor is not None:
        profit_factor = round(profit_factor, 6)

    avg_position_size = safe_div(total_volume, num_trades) if num_trades else None
    if avg_position_size is not None:
        avg_position_size = round(avg_position_size, 2)

    avg_holding_duration = None
    if holding_count > 0:
        avg_holding_duration = timedelta(seconds=total_holding_seconds / holding_count)

    if num_trades < MIN_CATEGORY_TRADES:
        return None

    return {
        "wallet": wallet,
        "category": category,
        "snapshot_date": today,
        "num_trades": num_trades,
        "total_volume": round(total_volume, 2),
        "total_cost_basis": round(total_cost_basis, 2),
        "total_pnl": round(total_pnl, 2),
        "total_realized_pnl": round(total_realized_pnl, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "roi": roi,
        "win_rate": win_rate,
        "num_resolved_positions": resolved_total,
        "profit_factor": profit_factor,
        "avg_position_size": avg_position_size,
        "avg_holding_duration": avg_holding_duration,
        "is_specialist": False,
        "category_rank": None,
    }


@transformer
def transform_df(
    positions: DataFrame,
    trades: DataFrame,
    market_categories: DataFrame,
    *args,
    **kwargs,
) -> dict:
    if market_categories.empty:
        print("No market categories available — skipping")
        return {"analytics": DataFrame(), "rankings": DataFrame()}

    cat_map = dict(zip(market_categories["market_id"], market_categories["category"]))

    positions = positions.copy()
    if not positions.empty and "market_id" in positions.columns:
        positions["_category"] = positions["market_id"].map(cat_map)
        positions = positions[positions["_category"].notna()].copy()
    else:
        positions = DataFrame(columns=list(positions.columns) + ["_category"])

    trades = trades.copy()
    if not trades.empty and "market_id" in trades.columns:
        trades["_category"] = trades["market_id"].map(cat_map)
        trades = trades[trades["_category"].notna()].copy()
    else:
        trades = DataFrame(columns=list(trades.columns) + ["_category"])

    all_wallets = set()
    if not positions.empty:
        all_wallets.update(positions["wallet"].unique())
    if not trades.empty:
        all_wallets.update(trades["wallet"].unique())

    rows: list[dict] = []
    wallet_category_groups: dict[tuple[str, str], tuple[DataFrame, DataFrame]] = {}

    if not positions.empty:
        for (wallet, cat), grp in positions.groupby(["wallet", "_category"]):
            key = (wallet, cat)
            if key not in wallet_category_groups:
                wallet_category_groups[key] = (DataFrame(), DataFrame())
            p, t = wallet_category_groups[key]
            wallet_category_groups[key] = (grp, t)

    if not trades.empty:
        for (wallet, cat), grp in trades.groupby(["wallet", "_category"]):
            key = (wallet, cat)
            if key not in wallet_category_groups:
                wallet_category_groups[key] = (DataFrame(), DataFrame())
            p, t = wallet_category_groups[key]
            wallet_category_groups[key] = (p, grp)

    print(f"Computing category metrics for {len(wallet_category_groups)} (wallet, category) pairs")
    for (wallet, cat), (p, t) in sorted(wallet_category_groups.items()):
        result = compute_category_metrics_for_wallet(wallet, cat, t, p)
        if result is not None:
            rows.append(result)

    analytics_df = DataFrame(rows) if rows else DataFrame()

    if analytics_df.empty:
        print("No category analytics rows produced")
        return {"analytics": DataFrame(), "rankings": DataFrame()}

    # Mark specialists per category
    for cat in analytics_df["category"].unique():
        mask = analytics_df["category"] == cat
        cat_data = analytics_df[mask]
        if len(cat_data) < 2:
            continue
        median_roi = cat_data["roi"].median()
        median_volume = cat_data["total_volume"].median()
        specialist_mask = mask & (
            (analytics_df["roi"].fillna(-9999) > median_roi)
            & (analytics_df["total_volume"].fillna(0) >= median_volume)
        )
        analytics_df.loc[specialist_mask, "is_specialist"] = True

    # Rank within each category by ROI
    analytics_df["category_rank"] = analytics_df.groupby("category")["roi"].rank(
        ascending=False, method="dense"
    ).astype(int)

    # Build rankings
    ranking_rows: list[dict] = []
    for cat in analytics_df["category"].unique():
        top_50 = analytics_df[analytics_df["category"] == cat].nsmallest(50, "category_rank")
        for _, r in top_50.iterrows():
            ranking_rows.append({
                "wallet": r["wallet"],
                "category": cat,
                "snapshot_date": r["snapshot_date"],
                "list_type": "top_50",
                "rank": int(r["category_rank"]),
                "roi": r.get("roi"),
                "win_rate": r.get("win_rate"),
                "total_pnl": r.get("total_pnl"),
                "num_trades": r.get("num_trades"),
                "total_volume": r.get("total_volume"),
            })

        specialists = analytics_df[
            (analytics_df["category"] == cat) & (analytics_df["is_specialist"])
        ]
        for i, (_, r) in enumerate(specialists.iterrows(), 1):
            ranking_rows.append({
                "wallet": r["wallet"],
                "category": cat,
                "snapshot_date": r["snapshot_date"],
                "list_type": "specialists",
                "rank": i,
                "roi": r.get("roi"),
                "win_rate": r.get("win_rate"),
                "total_pnl": r.get("total_pnl"),
                "num_trades": r.get("num_trades"),
                "total_volume": r.get("total_volume"),
            })

    rankings_df = DataFrame(ranking_rows) if ranking_rows else DataFrame()
    print(f"Category analytics: {len(analytics_df)} rows, {len(rankings_df)} ranking rows")
    return {"analytics": analytics_df, "rankings": rankings_df}


@test
def test_output(result) -> None:
    assert "analytics" in result, "Missing analytics"
    assert "rankings" in result, "Missing rankings"
