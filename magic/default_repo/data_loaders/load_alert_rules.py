from pandas import DataFrame
from sqlalchemy import create_engine, text

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

from default_repo.utils.db_helpers import DATABASE_URL

EXPECTED_COLUMNS = [
    "id", "wallet", "min_score", "min_position_size", "min_liquidity",
    "cooldown_minutes", "discord_webhook_url", "active",
]


def _convert_uuids(df: DataFrame) -> DataFrame:
    """Convert UUID columns to strings for Parquet compatibility."""
    for col in df.select_dtypes(include=["object"]).columns:
        sample = df[col].dropna()
        if not sample.empty and hasattr(sample.iloc[0], "hex"):
            df[col] = df[col].astype(str)
    return df


@data_loader
def load_data(*args, **kwargs) -> DataFrame:
    """Load active alert rules from alert_rules."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT * FROM alert_rules WHERE active = true
            ORDER BY wallet NULLS LAST
        """)).mappings().all()

    engine.dispose()

    if not rows:
        return DataFrame(columns=EXPECTED_COLUMNS)

    df = DataFrame([dict(r) for r in rows])
    df = _convert_uuids(df)
    print(f"Loaded {len(df)} alert rules")
    return df


@test
def test_output(df) -> None:
    assert df is not None, "Output is undefined"
