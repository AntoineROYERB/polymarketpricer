"""Shared database helpers for ETL pipeline blocks."""

import math

from pandas import isna
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://app:devpassword@postgres:5432/polymarket"


def load_condition_map() -> dict:
    """Build condition_id → market_id mapping from the markets table."""
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, condition_id FROM markets WHERE condition_id IS NOT NULL")
        )
        mapping = {row.condition_id: row.id for row in rows}
    engine.dispose()
    return mapping


NAT_LIKE = frozenset({"NaT", "nat", "NaN", "nan", "inf", "-inf"})


def safe_value(v):
    """Convert numpy NaN / inf / NaT to SQL NULL."""
    if v is None or (not isinstance(v, str) and isna(v)):
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, str) and v in NAT_LIKE:
        return None
    return v
