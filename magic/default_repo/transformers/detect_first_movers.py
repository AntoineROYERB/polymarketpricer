"""Detect wallets trading on markets less than 24 hours old."""
from datetime import datetime, timedelta, timezone

from pandas import DataFrame

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

ALERT_COLS = [
    "wallet", "market_id", "action", "price", "position_size",
    "wallet_score", "category", "market_question", "detected_at",
]
FIRST_MOVER_MARKET_AGE_HOURS = 24
FIRST_MOVER_MIN_SCORE = 60


@transformer
def detect_first_movers(trades: DataFrame, wallet_scores: DataFrame, markets: DataFrame, *args, **kwargs) -> DataFrame:
    now = datetime.now(timezone.utc)
    market_age_cutoff = now - timedelta(hours=FIRST_MOVER_MARKET_AGE_HOURS)

    young_markets = markets[markets["created_at"] >= market_age_cutoff]
    if young_markets.empty:
        return DataFrame(columns=ALERT_COLS)

    first_mover_trades = trades[trades["market_id"].isin(young_markets["id"])]
    if first_mover_trades.empty:
        return DataFrame(columns=ALERT_COLS)

    first_mover_trades = first_mover_trades.merge(
        wallet_scores[["wallet", "wallet_score"]], on="wallet", how="inner",
    )
    first_mover_trades = first_mover_trades[
        first_mover_trades["wallet_score"] >= FIRST_MOVER_MIN_SCORE
    ]
    first_mover_trades = first_mover_trades.drop_duplicates(subset=["wallet", "market_id"])
    first_mover_trades = first_mover_trades.merge(
        markets[["id", "question", "mapped_category"]],
        left_on="market_id", right_on="id", how="left",
    )

    alert_rows = []
    for _, row in first_mover_trades.iterrows():
        alert_rows.append({
            "wallet": row["wallet"],
            "market_id": row["market_id"],
            "action": "FIRST_MOVER",
            "price": float(row.get("price", 0) or 0),
            "position_size": float(row.get("amount_usd", 0) or 0),
            "wallet_score": float(row.get("wallet_score", 0)),
            "category": row.get("mapped_category", "unknown"),
            "market_question": row.get("question", ""),
            "detected_at": now,
        })

    return DataFrame(alert_rows)


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
