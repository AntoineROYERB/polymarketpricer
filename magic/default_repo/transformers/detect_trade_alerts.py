"""Detect smart money activity from recent trades directly."""
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
TRADE_ALERT_WINDOW_MINUTES = 1440
MIN_POSITION_SIZE_USD = 1000
MIN_WALLET_SCORE = 70


@transformer
def detect_alerts(trades: DataFrame, wallet_scores: DataFrame, markets: DataFrame, *args, **kwargs) -> DataFrame:
    if trades.empty:
        return DataFrame(columns=ALERT_COLS)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=TRADE_ALERT_WINDOW_MINUTES)
    recent = trades[trades["timestamp"] >= cutoff].copy()
    if recent.empty:
        return DataFrame(columns=ALERT_COLS)

    recent = recent.merge(
        wallet_scores[["wallet", "wallet_score"]], on="wallet", how="inner",
    )
    recent = recent[recent["wallet_score"] >= MIN_WALLET_SCORE]
    recent = recent.merge(
        markets[["id", "question", "mapped_category", "liquidity_usd"]],
        left_on="market_id", right_on="id", how="left",
    )

    alert_rows = []
    for _, row in recent.iterrows():
        position_size = float(row.get("amount_usd", 0) or 0)
        if position_size < MIN_POSITION_SIZE_USD:
            continue
        alert_rows.append({
            "wallet": row["wallet"],
            "market_id": row["market_id"],
            "action": f"TRADE_{row['side']}".upper(),
            "price": float(row.get("price", 0) or 0),
            "position_size": position_size,
            "wallet_score": float(row.get("wallet_score", 0)),
            "category": row.get("mapped_category", "unknown"),
            "market_question": row.get("question", ""),
            "detected_at": now,
        })

    return DataFrame(alert_rows)


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
