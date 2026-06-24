from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_loader
def load_data_from_api(active_wallets: DataFrame, *args, **kwargs) -> DataFrame:
    if active_wallets.empty:
        return DataFrame()

    wallets_list = active_wallets["wallet"].tolist()
    engine = create_engine(DATABASE_URL)
    df = read_sql(
        text("""
            SELECT
                p.wallet, p.market_id, p.realized_pnl, p.unrealized_pnl, p.total_pnl,
                p.status, p.entry_time, p.exit_time,
                wps.total_pnl AS pnl_accurate,
                wps.total_realized_pnl AS realized_accurate,
                wps.total_unrealized_pnl AS unrealized_accurate,
                wps.category_breakdown
            FROM positions p
            LEFT JOIN wallet_pnl_snapshots wps
                ON p.wallet = wps.wallet
                AND wps.snapshot_date = CURRENT_DATE
            WHERE p.wallet = ANY(:wallets)
              AND p.entry_time >= CURRENT_DATE - INTERVAL '90 days'
        """),
        engine,
        params={"wallets": wallets_list},
    )
    engine.dispose()
    print(f"Loaded {len(df)} position rows for recent wallets")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
