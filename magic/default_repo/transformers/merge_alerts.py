"""Merge alerts from position changes, trade alerts, and first-mover detection."""
from pandas import DataFrame, concat

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

ALERT_COLS = [
    "wallet", "market_id", "action", "price", "position_size",
    "wallet_score", "category", "market_question", "detected_at",
]


@transformer
def merge_alerts(
    position_alerts: DataFrame,
    trade_alerts: DataFrame,
    first_mover_alerts: DataFrame,
    *args, **kwargs,
) -> DataFrame:
    frames = []
    if not position_alerts.empty:
        frames.append(position_alerts[ALERT_COLS])
    if not trade_alerts.empty:
        frames.append(trade_alerts[ALERT_COLS])
    if not first_mover_alerts.empty:
        frames.append(first_mover_alerts[ALERT_COLS])

    if not frames:
        return DataFrame(columns=ALERT_COLS)

    merged = concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["wallet", "market_id", "action"])
    print(f"Merged alerts: {len(merged)} total from {len(frames)} sources")
    return merged


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
