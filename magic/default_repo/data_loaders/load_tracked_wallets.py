from pandas import DataFrame, read_sql
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL
from default_repo.utils.sync_mode import get_sync_cutoff, is_full_sync

BATCH_SIZE = 5000


@data_loader
def load_data_from_api(**kwargs) -> DataFrame:
    tier = kwargs.get("TIER", 1)
    batch = kwargs.get("BATCH", 0)
    cutoff = get_sync_cutoff(tier) if not is_full_sync() else None

    engine = create_engine(DATABASE_URL)
    offset = batch * BATCH_SIZE

    if cutoff is None:
        df = read_sql(
            text("""
                SELECT wallet, main_wallet
                FROM wallets
                WHERE is_tracked = true
                ORDER BY wallet
                LIMIT :limit OFFSET :offset
            """),
            engine,
            params={"limit": BATCH_SIZE, "offset": offset},
        )
    else:
        df = read_sql(
            text("""
                SELECT wallet, main_wallet
                FROM wallets
                WHERE is_tracked = true
                  AND (last_position_sync IS NULL OR last_position_sync < :cutoff)
                ORDER BY last_position_sync NULLS FIRST
                LIMIT :limit OFFSET :offset
            """),
            engine,
            params={"cutoff": cutoff, "limit": BATCH_SIZE, "offset": offset},
        )

    engine.dispose()
    print(f"Batch {batch}: {len(df)} tracked wallets (tier {tier})")
    return df


@test
def test_output(df) -> None:
    assert df is not None, 'The output is undefined'
