from datetime import datetime, timezone
from pandas import DataFrame
from sqlalchemy import create_engine, text

from default_repo.utils.db_helpers import safe_value

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


def upsert_positions(engine, df: DataFrame):
    if df.empty:
        return
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO positions (wallet, market_id, outcome_id, side, status,
                                           avg_entry_price, shares, entry_time, exit_time,
                                           realized_pnl, unrealized_pnl, total_pnl)
                    VALUES (:wallet, :market_id, :outcome_id, :side, :status,
                            :avg_entry_price, :shares, :entry_time, :exit_time,
                            :realized_pnl, :unrealized_pnl, :total_pnl)
                    ON CONFLICT (wallet, market_id) DO UPDATE SET
                        outcome_id = EXCLUDED.outcome_id,
                        side = EXCLUDED.side,
                        status = EXCLUDED.status,
                        avg_entry_price = EXCLUDED.avg_entry_price,
                        shares = EXCLUDED.shares,
                        entry_time = COALESCE(positions.entry_time, EXCLUDED.entry_time),
                        exit_time = EXCLUDED.exit_time,
                        realized_pnl = EXCLUDED.realized_pnl,
                        unrealized_pnl = EXCLUDED.unrealized_pnl,
                        total_pnl = EXCLUDED.total_pnl
                """),
                {
                    "wallet": row["wallet"],
                    "market_id": row["market_id"],
                    "outcome_id": safe_value(row.get("outcome_id")),
                    "side": safe_value(row.get("side")),
                    "status": safe_value(row.get("status", "OPEN")),
                    "avg_entry_price": safe_value(row.get("avg_entry_price")),
                    "shares": safe_value(row.get("shares")),
                    "entry_time": safe_value(row.get("entry_time")),
                    "exit_time": safe_value(row.get("exit_time")),
                    "realized_pnl": safe_value(row.get("realized_pnl")),
                    "unrealized_pnl": safe_value(row.get("unrealized_pnl")),
                    "total_pnl": safe_value(row.get("total_pnl")),
                },
            )


def insert_position_history(engine, df: DataFrame):
    if df.empty:
        return
    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO position_history (wallet, market_id, outcome_id, side,
                                                  shares_before, shares_after, pnl_change, recorded_at)
                    VALUES (:wallet, :market_id, :outcome_id, :side,
                            :shares_before, :shares_after, :pnl_change, :recorded_at)
                """),
                {
                    "wallet": row["wallet"],
                    "market_id": row["market_id"],
                    "outcome_id": safe_value(row.get("outcome_id")),
                    "side": safe_value(row.get("side")),
                    "shares_before": safe_value(row.get("shares_before")),
                    "shares_after": safe_value(row.get("shares_after")),
                    "pnl_change": safe_value(row.get("pnl_change")),
                    "recorded_at": safe_value(row.get("recorded_at", datetime.now(timezone.utc))),
                },
            )


@data_exporter
def export_data(data: dict, **kwargs) -> None:
    print(f"Exporting {len(data['positions'])} positions, {len(data['position_history'])} history rows")
    engine = create_engine(DATABASE_URL)
    upsert_positions(engine, data["positions"])
    insert_position_history(engine, data["position_history"])
    engine.dispose()
    print("Position export complete")
