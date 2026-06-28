from datetime import date
from decimal import Decimal
from statistics import median as stat_median, stdev as stat_stdev
from collections import defaultdict, deque
from typing import NamedTuple

from pandas import DataFrame, to_numeric

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

RESOLUTION_PRICE_WINNER = Decimal("1.0")
RESOLUTION_PRICE_LOSER = Decimal("0.0")

EMPTY_SNAPSHOT_COLUMNS = [
    "wallet", "snapshot_date", "avg_edge", "median_edge",
    "edge_consistency", "edge_volatility", "edge_score",
    "num_edge_trades", "positive_edge_trades", "negative_edge_trades",
]


class WalletEdgeAgg(NamedTuple):
    edges: list[Decimal]
    positives: int
    negatives: int


def resolve_price(outcome_winner: bool | None) -> Decimal:
    return RESOLUTION_PRICE_WINNER if outcome_winner is True else RESOLUTION_PRICE_LOSER


def _build_resolution_prices(outcomes: DataFrame) -> dict[str, dict[str, Decimal]]:
    prices: dict[str, dict[str, Decimal]] = {}
    for _, row in outcomes.iterrows():
        market_id = str(row["market_id"])
        outcome_id = str(row["outcome_id"])
        prices.setdefault(market_id, {})[outcome_id] = resolve_price(row.get("winner"))
    return prices


def compute_wallet_edge(
    trades: DataFrame,
    outcomes_or_prices: DataFrame | dict[str, dict[str, Decimal]],
) -> list[dict]:
    resolution_prices = (
        _build_resolution_prices(outcomes_or_prices)
        if isinstance(outcomes_or_prices, DataFrame)
        else outcomes_or_prices
    )
    groups: dict[tuple[str, str, str], deque] = defaultdict(deque)
    for _, row in trades.iterrows():
        key = (str(row["wallet"]), str(row["market_id"]), str(row["outcome_id"]))
        groups[key].append(row.to_dict())

    edge_results: list[dict] = []

    for (wallet, market_id, outcome_id), trade_list in groups.items():
        buy_queue: deque = deque()
        sell_queue: deque = deque()

        for trade in trade_list:
            ttype = str(trade.get("type", "")).strip().upper()
            if ttype == "BUY":
                buy_queue.append(trade)
            elif ttype == "SELL":
                sell_queue.append(trade)

        while buy_queue:
            buy = buy_queue.popleft()
            entry_price = Decimal(str(buy.get("price", 0)))

            if entry_price <= 0:
                continue

            matched_sell = sell_queue.popleft() if sell_queue else None
            if matched_sell is not None:
                edge_price = Decimal(str(matched_sell.get("price", 0)))
            else:
                edge_price = resolution_prices.get(market_id, {}).get(outcome_id)

            if edge_price is None:
                continue

            edge = (edge_price - entry_price) / entry_price

            edge_results.append({
                "wallet": wallet,
                "market_id": market_id,
                "outcome_id": outcome_id,
                "trade_id": str(buy.get("trade_id", "")),
                "entry_price": entry_price,
                "edge_price": edge_price,
                "edge": edge,
                "size": Decimal(str(buy.get("size", 0))),
                "is_positive": edge > 0,
                "had_sell": matched_sell is not None,
            })

    return edge_results


def _normalize_columns(df: DataFrame) -> DataFrame:
    for col in ["price", "size", "amount_usd", "shares"]:
        if col in df.columns:
            df[col] = to_numeric(df[col], errors="coerce").fillna(0)
    df["created_at"] = df["created_at"].astype("datetime64[ns]")
    return df


def _aggregate_wallet_edges(edge_records: list[dict]) -> dict[str, WalletEdgeAgg]:
    wallet_data: dict[str, WalletEdgeAgg] = {}
    for rec in edge_records:
        w = rec["wallet"]
        if w not in wallet_data:
            wallet_data[w] = WalletEdgeAgg([], 0, 0)
        agg = wallet_data[w]
        wallet_data[w] = WalletEdgeAgg(
            agg.edges + [rec["edge"]],
            agg.positives + (1 if rec["is_positive"] else 0),
            agg.negatives + (0 if rec["is_positive"] else 1),
        )
    return wallet_data


def _compute_normalization_range(wallet_data: dict[str, WalletEdgeAgg]) -> tuple[float, float]:
    all_edge_values = [float(e) for agg in wallet_data.values() for e in agg.edges]
    if not all_edge_values:
        return 0.0, 1.0
    min_edge = min(all_edge_values)
    max_edge = max(all_edge_values)
    edge_range = max_edge - min_edge if max_edge != min_edge else 1.0
    return min_edge, edge_range


def _build_snapshot_rows(
    wallet_data: dict[str, WalletEdgeAgg],
    snapshot_date: date,
    min_edge: float,
    edge_range: float,
) -> list[dict]:
    rows = []
    for wallet, agg in wallet_data.items():
        float_edges = [float(e) for e in agg.edges]
        avg_edge = sum(float_edges) / len(float_edges)
        med_edge = stat_median(float_edges) if len(float_edges) > 1 else float_edges[0]
        vol = stat_stdev(float_edges) if len(float_edges) > 1 else None
        consistency = agg.positives / len(float_edges)
        edge_score = (avg_edge - min_edge) / edge_range

        rows.append({
            "wallet": wallet,
            "snapshot_date": snapshot_date,
            "avg_edge": avg_edge,
            "median_edge": med_edge,
            "edge_consistency": consistency,
            "edge_volatility": vol,
            "edge_score": edge_score,
            "num_edge_trades": len(float_edges),
            "positive_edge_trades": agg.positives,
            "negative_edge_trades": agg.negatives,
        })
    return rows


@transformer
def compute_edges(trades_df: DataFrame, outcomes_df: DataFrame, *args, **kwargs) -> DataFrame:
    if trades_df.empty:
        return DataFrame(columns=EMPTY_SNAPSHOT_COLUMNS)

    trades_df = _normalize_columns(trades_df)

    resolution_prices = _build_resolution_prices(outcomes_df)
    edge_records = compute_wallet_edge(trades_df, resolution_prices)

    if not edge_records:
        return DataFrame(columns=EMPTY_SNAPSHOT_COLUMNS)

    wallet_data = _aggregate_wallet_edges(edge_records)
    min_edge, edge_range = _compute_normalization_range(wallet_data)
    snapshot_rows = _build_snapshot_rows(wallet_data, date.today(), min_edge, edge_range)

    result = DataFrame(snapshot_rows)
    print(f"Computed edge snapshots for {len(result)} wallets "
          f"(from {len(edge_records)} trade edges)")
    return result


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert "wallet" in df.columns
        assert "avg_edge" in df.columns
        assert "edge_score" in df.columns
        assert "num_edge_trades" in df.columns
        assert df["edge_score"].between(0, 1, inclusive="both").all(), \
            "edge_score must be in [0, 1]"
        assert df["avg_edge"].notna().all(), "avg_edge must not be NULL"
        assert df["num_edge_trades"].ge(1).all(), \
            "Each wallet must have at least 1 edge trade"
