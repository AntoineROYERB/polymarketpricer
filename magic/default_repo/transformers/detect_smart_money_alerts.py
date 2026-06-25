from datetime import datetime, timezone

from pandas import DataFrame, to_numeric

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

ALERT_COLS = [
    "wallet", "market_id", "action", "price", "position_size",
    "wallet_score", "category", "market_question", "detected_at",
]


def classify_action(shares_before, shares_after):
    before = float(shares_before or 0)
    after = float(shares_after or 0)

    if before == 0 and after > 0:
        return "NEW_POSITION"
    if after > before:
        return "POSITION_INCREASE"
    if after < before and after > 0:
        return "POSITION_DECREASE"
    if after == 0 and before > 0:
        return "FULL_EXIT"
    return None


def get_applicable_rule(wallet: str, rules_df: DataFrame, market_volume: float = 0) -> dict:
    wallet_rule = rules_df[rules_df["wallet"] == wallet]
    if not wallet_rule.empty:
        return wallet_rule.iloc[0].to_dict()
    global_rule = rules_df[rules_df["wallet"].isna()]
    if not global_rule.empty:
        return global_rule.iloc[0].to_dict()

    if market_volume < 100_000:
        return {"min_score": 0.60, "min_position_size": 200, "min_liquidity": 500, "cooldown_minutes": 15}
    if market_volume < 1_000_000:
        return {"min_score": 0.80, "min_position_size": 500, "min_liquidity": 1000, "cooldown_minutes": 15}
    return {"min_score": 0.85, "min_position_size": 1000, "min_liquidity": 2000, "cooldown_minutes": 15}


@transformer
def detect_alerts(changes: DataFrame, scores: DataFrame, rules: DataFrame, *args, **kwargs) -> DataFrame:
    if changes.empty:
        print("No position changes to process")
        return DataFrame(columns=ALERT_COLS)

    now = datetime.now(timezone.utc)

    changes = changes.merge(scores, on="wallet", how="left", suffixes=("", "_score"))
    changes["wallet_score"] = to_numeric(
        changes.get("wallet_score"), errors="coerce"
    ).fillna(0)

    changes["shares_before"] = to_numeric(changes["shares_before"], errors="coerce").fillna(0)
    changes["shares_after"] = to_numeric(changes["shares_after"], errors="coerce").fillna(0)
    if "liquidity_usd" in changes.columns:
        changes["liquidity_usd"] = to_numeric(
            changes["liquidity_usd"], errors="coerce"
        ).fillna(0)

    alert_rows = []

    for _, row in changes.iterrows():
        action = classify_action(row["shares_before"], row["shares_after"])
        if action is None:
            continue

        rule = get_applicable_rule(row["wallet"], rules)

        if float(row.get("wallet_score", 0)) < float(rule.get("min_score", 0.80)):
            continue

        position_size = abs(
            float(row["shares_after"]) - float(row["shares_before"])
        )
        if position_size < float(rule.get("min_position_size", 500)):
            continue

        liquidity = float(row.get("liquidity_usd", 0) or 0)
        if liquidity < float(rule.get("min_liquidity", 1000)):
            continue

        alert_rows.append({
            "wallet": row["wallet"],
            "market_id": row["market_id"],
            "action": action,
            "price": 0.0,
            "position_size": position_size,
            "wallet_score": float(row.get("wallet_score", 0)),
            "category": row.get("category", "unknown"),
            "market_question": row.get("market_question", ""),
            "detected_at": now,
        })

    print(f"Detected {len(alert_rows)} alerts from {len(changes)} position changes")
    return DataFrame(alert_rows) if alert_rows else DataFrame(columns=ALERT_COLS)


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert "action" in df.columns, "Missing action column"
        valid_actions = {
            "NEW_POSITION", "POSITION_INCREASE",
            "POSITION_DECREASE", "FULL_EXIT",
        }
        assert df["action"].isin(valid_actions).all(), "Invalid action value"
