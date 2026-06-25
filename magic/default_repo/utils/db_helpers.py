"""Shared database helpers for ETL pipeline blocks."""

import functools
import math
import os

from pandas import isna
from sqlalchemy import create_engine, text

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://app:devpassword@postgres:5432/polymarket",
)
# Mage blocks use synchronous SQLAlchemy — replace async driver with sync driver.
# The FastAPI backend (app/) uses its own async engine from app/db/engine.py.
DATABASE_URL = _DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


@functools.lru_cache(maxsize=1)
def load_condition_map() -> dict:
    """Build condition_id → market_id mapping from the markets table.

    Cached per process (single pipeline run) via lru_cache.
    Three callers (positions, trades, activity) all run within the same
    pipeline sequentially - caching eliminates 2 of 3 DB queries.
    """
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
