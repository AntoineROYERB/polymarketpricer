from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.sync_mode import get_sync_cutoff, is_full_sync

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    tier = kwargs.get("TIER", 1)
    cutoff = get_sync_cutoff(tier) if not is_full_sync() else None

    engine = create_engine(DATABASE_URL)

    if cutoff is None:
        df = read_sql(
            text("SELECT wallet, main_wallet FROM wallets WHERE is_tracked = true"),
            engine,
        )
    else:
        df = read_sql(
            text("""
                SELECT wallet, main_wallet
                FROM wallets
                WHERE is_tracked = true
                  AND (last_trade_sync IS NULL OR last_trade_sync < :cutoff)
                ORDER BY last_trade_sync NULLS FIRST
            """),
            engine,
            params={"cutoff": cutoff},
        )

    engine.dispose()
    print(f"Loaded {len(df)} tracked wallets for trade sync (tier {tier})")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
