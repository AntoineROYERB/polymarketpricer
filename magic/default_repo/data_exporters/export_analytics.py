import math

from pandas import DataFrame, isna
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


def _val(v):
    """Convert numpy NaN to SQL NULL."""
    if v is None or (not isinstance(v, str) and isna(v)):
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


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
        for _, row in df.iterrows():
            params = {}
            for c in STR_COLS:
                params[c] = row.get(c)
            for c in INT_COLS:
                v = row.get(c)
                params[c] = _val(v)
            for c in NUM_COLS:
                params[c] = _val(row.get(c))
            params["snapshot_date"] = row["snapshot_date"]
            params["avg_holding_duration"] = _val(row.get("avg_holding_duration"))
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
                    ) ON CONFLICT (wallet, snapshot_date) DO UPDATE SET
                        total_pnl = EXCLUDED.total_pnl,
                        total_realized_pnl = EXCLUDED.total_realized_pnl,
                        total_unrealized_pnl = EXCLUDED.total_unrealized_pnl,
                        roi = EXCLUDED.roi,
                        total_volume = EXCLUDED.total_volume,
                        total_cost_basis = EXCLUDED.total_cost_basis,
                        win_rate = EXCLUDED.win_rate,
                        num_trades = EXCLUDED.num_trades,
                        num_resolved_positions = EXCLUDED.num_resolved_positions,
                        profit_factor = EXCLUDED.profit_factor,
                        sharpe_ratio = EXCLUDED.sharpe_ratio,
                        max_drawdown = EXCLUDED.max_drawdown,
                        avg_position_size = EXCLUDED.avg_position_size,
                        avg_holding_duration = EXCLUDED.avg_holding_duration,
                        consistency_score = EXCLUDED.consistency_score,
                        experience_score = EXCLUDED.experience_score,
                        wallet_score = EXCLUDED.wallet_score
                """),
                params,
            )
    engine.dispose()
    print("Analytics export complete")
