from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"
EXPECTED_COLUMNS = ["wallet", "wallet_score"]


@data_loader
def load_data(*args, **kwargs) -> DataFrame:
    """Load latest wallet scores from wallet_analytics."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT ON (wallet) wallet, wallet_score
            FROM wallet_analytics
            ORDER BY wallet, snapshot_date DESC
        """)).mappings().all()

    engine.dispose()

    if not rows:
        return DataFrame(columns=EXPECTED_COLUMNS)

    df = DataFrame([dict(r) for r in rows])
    print(f"Loaded {len(df)} wallet scores")
    return df


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
