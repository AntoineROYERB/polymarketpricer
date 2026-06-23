from datetime import datetime, timezone
from pandas import DataFrame, isna
from sqlalchemy import create_engine, text

from default_repo.utils.db_helpers import safe_value

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"

POS_COLS = ["wallet", "market_id", "outcome_id", "side", "status",
            "avg_entry_price", "shares", "entry_time", "exit_time",
            "realized_pnl", "unrealized_pnl", "total_pnl"]


def detect_changes(current: DataFrame, previous: DataFrame) -> tuple[DataFrame, DataFrame]:
    now = datetime.now(timezone.utc)

    if current.empty or "entry_time" not in current.columns:
        return DataFrame(columns=POS_COLS), DataFrame(
            columns=["wallet", "market_id", "outcome_id", "side",
                     "shares_before", "shares_after", "pnl_change", "recorded_at"])

    if previous.empty:
        current["entry_time"] = current["entry_time"].fillna(now)
        current["status"] = "OPEN"
        return current, DataFrame(columns=["wallet", "market_id", "outcome_id", "side",
                                            "shares_before", "shares_after", "pnl_change",
                                            "recorded_at"])

    merged = current.merge(
        previous,
        on=["wallet", "market_id"],
        how="outer",
        suffixes=("_new", "_old"),
        indicator=True,
    )

    history_rows = []
    positions_out = []

    for _, row in merged.iterrows():
        source = row["_merge"]

        if source == "left_only":
            row["entry_time"] = safe_value(row.get("entry_time_new")) or now
            row["exit_time"] = None
            row["status"] = "OPEN"
            row["outcome_id"] = safe_value(row.get("outcome_id_new"))
            row["side"] = safe_value(row.get("side_new"))
            row["avg_entry_price"] = safe_value(row.get("avg_entry_price_new"))
            row["shares"] = safe_value(row.get("shares_new"))
            row["realized_pnl"] = safe_value(row.get("realized_pnl_new"))
            row["unrealized_pnl"] = safe_value(row.get("unrealized_pnl_new"))
            row["total_pnl"] = safe_value(row.get("total_pnl_new"))
            positions_out.append(row)

        elif source == "right_only":
            row["entry_time"] = safe_value(row.get("entry_time_old"))
            row["exit_time"] = now
            row["status"] = "CLOSED"
            row["shares"] = 0
            row["outcome_id"] = safe_value(row.get("outcome_id_old"))
            row["side"] = safe_value(row.get("side_old"))
            row["avg_entry_price"] = safe_value(row.get("avg_entry_price_old"))
            row["realized_pnl"] = safe_value(row.get("realized_pnl_old"))
            row["unrealized_pnl"] = safe_value(row.get("unrealized_pnl_old"))
            row["total_pnl"] = safe_value(row.get("total_pnl_old"))
            positions_out.append(row)

            history_rows.append({
                "wallet": row["wallet"],
                "market_id": row["market_id"],
                "outcome_id": safe_value(row.get("outcome_id_old")),
                "side": safe_value(row.get("side_old")),
                "shares_before": safe_value(row.get("shares_old")),
                "shares_after": 0,
                "pnl_change": safe_value(row.get("realized_pnl_new")) or 0,
            })

        else:
            shares_new = safe_value(row.get("shares_new")) or 0
            shares_old = safe_value(row.get("shares_old")) or 0
            if shares_new != shares_old:
                pnl_change = float(safe_value(row.get("realized_pnl_new")) or 0) - float(safe_value(row.get("realized_pnl_old")) or 0)
                history_rows.append({
                    "wallet": row["wallet"],
                    "market_id": row["market_id"],
                    "outcome_id": safe_value(row.get("outcome_id_new")) or safe_value(row.get("outcome_id_old")),
                    "side": safe_value(row.get("side_new")) or safe_value(row.get("side_old")),
                    "shares_before": shares_old,
                    "shares_after": shares_new,
                    "pnl_change": pnl_change,
                })
            row["entry_time"] = safe_value(row.get("entry_time_old")) or safe_value(row.get("entry_time_new")) or now
            row["exit_time"] = None
            row["status"] = "OPEN"
            row["outcome_id"] = safe_value(row.get("outcome_id_new")) or safe_value(row.get("outcome_id_old"))
            row["side"] = safe_value(row.get("side_new")) or safe_value(row.get("side_old"))
            row["avg_entry_price"] = safe_value(row.get("avg_entry_price_new")) or safe_value(row.get("avg_entry_price_old"))
            row["shares"] = shares_new
            row["realized_pnl"] = safe_value(row.get("realized_pnl_new")) or safe_value(row.get("realized_pnl_old"))
            row["unrealized_pnl"] = safe_value(row.get("unrealized_pnl_new")) or safe_value(row.get("unrealized_pnl_old"))
            row["total_pnl"] = safe_value(row.get("total_pnl_new")) or safe_value(row.get("total_pnl_old"))
            positions_out.append(row)

    positions_df = DataFrame(positions_out) if positions_out else DataFrame(
        columns=POS_COLS
    )
    history_df = DataFrame(history_rows) if history_rows else DataFrame(
        columns=["wallet", "market_id", "outcome_id", "side",
                 "shares_before", "shares_after", "pnl_change", "recorded_at"]
    )
    if not history_df.empty:
        history_df["recorded_at"] = now

    for col in ["entry_time", "exit_time"]:
        if col in positions_df.columns:
            positions_df[col] = [None if isna(x) else x for x in positions_df[col]]

    for c in POS_COLS:
        if c not in positions_df.columns:
            positions_df[c] = None

    return positions_df[POS_COLS], history_df


@transformer
def transform_df(positions: DataFrame, *args, **kwargs) -> dict:
    """Merge new positions from API with existing positions in DB to detect changes."""

    engine = create_engine(DATABASE_URL)
    previous = DataFrame()
    with engine.connect() as conn:
        existing = conn.execute(text("SELECT * FROM positions")).mappings().all()
        if existing:
            previous = DataFrame([dict(r) for r in existing])
    engine.dispose()

    print(f"Loaded {len(previous)} existing positions from DB for diff")

    positions_df, history_df = detect_changes(positions, previous)
    print(f"Position merge: {len(positions_df)} positions, {len(history_df)} history rows")
    return {"positions": positions_df, "position_history": history_df}


@test
def test_output(result) -> None:
    assert "positions" in result, "Missing positions"
    assert "position_history" in result, "Missing position_history"
