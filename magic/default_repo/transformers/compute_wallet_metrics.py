import math
from datetime import date, timedelta
from pandas import DataFrame, to_numeric, NaT, Timestamp

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


def safe_div(n, d):
    if d is None or d == 0:
        return None
    return n / d


MIN_RESOLVED_TRADES = 50
MIN_VOLUME_USD = 1000
MIN_HISTORY_DAYS = 90


def should_include(
    resolved_total: int,
    num_trades: int,
    total_volume: float,
    first_seen: date | None,
    today: date,
) -> bool:
    """Check if a wallet meets the minimum quality thresholds.

    Uses resolved trades when available, falls back to total trade count
    if the position resolution pipeline has not yet marked positions as RESOLVED.

    Returns True if the wallet should be included in analytics.
    """
    has_enough_trades = (
        resolved_total >= MIN_RESOLVED_TRADES
        or num_trades >= MIN_RESOLVED_TRADES
    )
    if not has_enough_trades:
        return False
    if total_volume < MIN_VOLUME_USD:
        return False
    if first_seen is not None:
        age_days = (today - first_seen).days
        if age_days < MIN_HISTORY_DAYS:
            return False
    return True


def compute_metrics_for_wallet(
    wallet: str,
    trades: DataFrame,
    positions: DataFrame,
    first_seen: date | None = None,
) -> dict | None:
    today = date.today()

    total_realized_pnl = 0
    total_unrealized_pnl = 0
    total_cost_basis = 0
    total_volume = 0
    num_trades = 0
    resolved_wins = 0
    resolved_total = 0
    gross_profit = 0
    gross_loss = 0
    trade_pnls: list[float] = []
    cumulative_pnl = 0
    peak = 0
    drawdowns: list[float] = []
    total_holding_seconds = 0.0
    holding_count = 0

    if not trades.empty:
        wt = trades[trades["wallet"] == wallet].copy()
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

        sorted_trades = wt.sort_values("timestamp")
        for _, t in sorted_trades.iterrows():
            trade_pnl = float(t.get("amount_usd", 0) or 0)
            fee = float(t.get("fee_usd", 0) or 0)
            net = trade_pnl - fee
            trade_pnls.append(net)
            cumulative_pnl += net
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            dd = (peak - cumulative_pnl) / peak if peak > 0 else 0
            drawdowns.append(dd)

    if not positions.empty:
        wp = positions[positions["wallet"] == wallet].copy()
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

        closed = resolved
        for _, p in closed.iterrows():
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

    sharpe_ratio = None
    if num_trades >= 10 and len(trade_pnls) > 1:
        avg_pnl = sum(trade_pnls) / len(trade_pnls)
        variance = sum((x - avg_pnl) ** 2 for x in trade_pnls) / (len(trade_pnls) - 1)
        stddev = math.sqrt(variance) if variance > 0 else 0
        if stddev > 0:
            raw = (avg_pnl / stddev) * math.sqrt(252)
            sharpe_ratio = round(max(min(raw, 100), -100), 6)

    max_drawdown = round(max(drawdowns), 6) if drawdowns else None

    avg_position_size = safe_div(total_volume, num_trades) if num_trades else None
    if avg_position_size is not None:
        avg_position_size = round(avg_position_size, 2)

    avg_holding_duration = None
    if holding_count > 0:
        avg_seconds = total_holding_seconds / holding_count
        avg_holding_duration = avg_seconds

    consistency_score = None
    if num_trades >= 10 and len(trade_pnls) > 1:
        mean_abs = sum(abs(x) for x in trade_pnls) / len(trade_pnls)
        if mean_abs > 0:
            variance = sum((x - sum(trade_pnls) / len(trade_pnls)) ** 2 for x in trade_pnls) / (len(trade_pnls) - 1)
            stddev = math.sqrt(variance)
            cv = stddev / mean_abs
            consistency_score = round(1 / (1 + cv), 6)

    experience_score = None
    trade_component = min(num_trades / 2000, 1.0)
    resolve_component = min(resolved_total / 100, 1.0)
    hold_component = 0.0
    if holding_count > 0:
        avg_days = total_holding_seconds / holding_count / 86400
        hold_component = min(avg_days / 60, 1.0)
    experience_score = round(
        0.5 * trade_component + 0.3 * resolve_component + 0.2 * hold_component, 6
    )

    if not should_include(resolved_total, num_trades, total_volume, first_seen, today):
        print(f"  filtering out {wallet}: "
              f"resolved={resolved_total}, volume={total_volume}, first_seen={first_seen}")
        return None

    return {
        "wallet": wallet,
        "snapshot_date": today,
        "total_pnl": round(total_pnl, 2),
        "total_realized_pnl": round(total_realized_pnl, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "roi": roi,
        "total_volume": round(total_volume, 2),
        "total_cost_basis": round(total_cost_basis, 2),
        "win_rate": win_rate,
        "num_trades": num_trades,
        "num_resolved_positions": resolved_total,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "avg_position_size": avg_position_size,
        "avg_holding_duration": avg_holding_duration,
        "consistency_score": consistency_score,
        "experience_score": experience_score,
        "wallet_score": None,
    }


def _compute_first_seen(trades: DataFrame, positions: DataFrame) -> dict[str, date]:
    """Build a mapping of wallet → earliest known activity date."""
    first_seen: dict[str, date] = {}

    if not trades.empty and "wallet" in trades.columns and "timestamp" in trades.columns:
        ts = trades[["wallet", "timestamp"]].copy()
        ts["timestamp"] = to_numeric(ts["timestamp"], errors="coerce")
        ts = ts.dropna(subset=["timestamp"])
        if not ts.empty:
            earliest = ts.groupby("wallet")["timestamp"].min()
            for wallet, ts_val in earliest.items():
                try:
                    first_seen[wallet] = Timestamp(ts_val).date()
                except Exception:
                    pass

    if not positions.empty and "wallet" in positions.columns and "entry_time" in positions.columns:
        ps = positions[["wallet", "entry_time"]].copy()
        ps["entry_time"] = to_numeric(ps["entry_time"], errors="coerce")
        ps = ps.dropna(subset=["entry_time"])
        if not ps.empty:
            earliest = ps.groupby("wallet")["entry_time"].min()
            for wallet, ts_val in earliest.items():
                try:
                    d = Timestamp(ts_val).date()
                    if wallet not in first_seen or d < first_seen[wallet]:
                        first_seen[wallet] = d
                except Exception:
                    pass

    return first_seen


@transformer
def transform_df(positions: DataFrame, trades: DataFrame, *args, **kwargs) -> DataFrame:
    wallets = set()
    if not positions.empty:
        wallets.update(positions["wallet"].unique())
    if not trades.empty:
        wallets.update(trades["wallet"].unique())

    wallet_first_seen = _compute_first_seen(trades, positions)

    sorted_wallets = sorted(wallets)
    print(f"Computing analytics for {len(sorted_wallets)} wallets")
    rows = []
    for i, w in enumerate(sorted_wallets, 1):
        fs = wallet_first_seen.get(w)
        result = compute_metrics_for_wallet(w, trades, positions, first_seen=fs)
        if result is not None:
            rows.append(result)
        if i % 50 == 0 or i == len(sorted_wallets):
            print(f"  computed wallet {i}/{len(sorted_wallets)}")

    print(f"Analytics computed: {len(rows)} wallets passed filters out of {len(sorted_wallets)}")
    return DataFrame(rows)


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
