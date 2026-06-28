from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    engine = create_engine(DATABASE_URL)
    df = read_sql(
        text("""
            SELECT
                wa.wallet,
                wa.snapshot_date,
                wa.total_pnl,
                wa.total_realized_pnl,
                wa.total_unrealized_pnl,
                wa.roi,
                wa.total_volume,
                wa.total_cost_basis,
                wa.win_rate,
                wa.num_trades,
                wa.num_resolved_positions,
                wa.profit_factor,
                wa.sharpe_ratio,
                wa.max_drawdown,
                wa.avg_position_size,
                wa.avg_holding_duration,
                wa.consistency_score,
                wa.experience_score,
                wa.wallet_score,
                COALESCE(wes.edge_score, 0) AS edge_score,
                COALESCE(wes.edge_consistency, 0) AS edge_consistency,
                COALESCE(wes.num_edge_trades, 0) AS num_edge_trades
            FROM wallet_analytics wa
            LEFT JOIN (
                SELECT DISTINCT ON (wallet)
                    wallet, edge_score, edge_consistency, num_edge_trades
                FROM wallet_edge_snapshots
                ORDER BY wallet, snapshot_date DESC
            ) wes ON wes.wallet = wa.wallet
            WHERE wa.snapshot_date = CURRENT_DATE
        """),
        engine,
    )
    engine.dispose()
    print(f"Loaded {len(df)} analytics records for today (with edge data)")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
