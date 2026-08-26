"""Shared Decimal conversion helpers."""

from decimal import Decimal
from typing import Any


def to_decimal(val: Any) -> Decimal:
    """Convert a value to Decimal, defaulting to 0 if None."""
    if val is None:
        return Decimal(0)
    return Decimal(str(val))


def to_optional_decimal(val: Any) -> Decimal | None:
    """Convert a value to Decimal, returning None if None."""
    if val is None:
        return None
    return Decimal(str(val))
