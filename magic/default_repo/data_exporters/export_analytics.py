from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_exporter
def export_data(df: DataFrame, **kwargs) -> None:
    if df.empty:
        return
    print(f"Exporting analytics for {len(df)} wallets")
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        for _, row in df.iterrows():
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
                {
                    "wallet": row["wallet"],
                    "snapshot_date": row["snapshot_date"],
                    "total_pnl": row.get("total_pnl"),
                    "total_realized_pnl": row.get("total_realized_pnl"),
                    "total_unrealized_pnl": row.get("total_unrealized_pnl"),
                    "roi": row.get("roi"),
                    "total_volume": row.get("total_volume"),
                    "total_cost_basis": row.get("total_cost_basis"),
                    "win_rate": row.get("win_rate"),
                    "num_trades": row.get("num_trades"),
                    "num_resolved_positions": row.get("num_resolved_positions"),
                    "profit_factor": row.get("profit_factor"),
                    "sharpe_ratio": row.get("sharpe_ratio"),
                    "max_drawdown": row.get("max_drawdown"),
                    "avg_position_size": row.get("avg_position_size"),
                    "avg_holding_duration": row.get("avg_holding_duration"),
                    "consistency_score": row.get("consistency_score"),
                    "experience_score": row.get("experience_score"),
                    "wallet_score": row.get("wallet_score"),
                },
            )
    engine.dispose()
    print("Analytics export complete")
