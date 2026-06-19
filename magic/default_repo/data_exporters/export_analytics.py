from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

from utils.db_helpers import safe_value

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


NUM_COLS = [
    "total_pnl", "total_realized_pnl", "total_unrealized_pnl",
    "roi", "total_volume", "total_cost_basis", "win_rate",
    "profit_factor", "sharpe_ratio", "max_drawdown",
    "avg_position_size", "consistency_score", "experience_score", "wallet_score",
]
STR_COLS = ["wallet"]
INT_COLS = ["num_trades", "num_resolved_positions"]


@data_exporter
def export_data(df: DataFrame, **kwargs) -> None:
    if df.empty:
        return
    print(f"Exporting analytics for {len(df)} wallets")
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        # Replace all rows for the current snapshot_date
        snapshot_dates = df["snapshot_date"].unique()
        for sd in snapshot_dates:
            conn.execute(
                text("DELETE FROM wallet_analytics WHERE snapshot_date = :sd"),
                {"sd": sd},
            )
            print(f"  cleared wallet_analytics for snapshot_date={sd}")

        for _, row in df.iterrows():
            params = {}
            for c in STR_COLS:
                params[c] = row.get(c)
            for c in INT_COLS:
                v = row.get(c)
                params[c] = safe_value(v)
            for c in NUM_COLS:
                params[c] = safe_value(row.get(c))
            params["snapshot_date"] = row["snapshot_date"]
            params["avg_holding_duration"] = safe_value(row.get("avg_holding_duration"))
            conn.execute(
                text("""
                    INSERT INTO wallet_analytics (
                        wallet, snapshot_date, total_pnl, total_realized_pnl, total_unrealized_pnl,
                        roi, total_volume, total_cost_basis, win_rate, num_trades,
                        num_resolved_positions, profit_factor, sharpe_ratio, max_drawdown,
                        avg_position_size, avg_holding_duration, consistency_score,
                        experience_score, wallet_score
                    ) VALUES (
                        :wallet, :snapshot_date, :total_pnl, :total_realized_pnl, :total_unrealized_pnl,
                        :roi, :total_volume, :total_cost_basis, :win_rate, :num_trades,
                        :num_resolved_positions, :profit_factor, :sharpe_ratio, :max_drawdown,
                        :avg_position_size, :avg_holding_duration, :consistency_score,
                        :experience_score, :wallet_score
                    )
                """),
                params,
            )
    engine.dispose()
    print("Analytics export complete")
