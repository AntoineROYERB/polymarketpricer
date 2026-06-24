"""Utility to determine sync cutoff with staggered margin."""

import os
from datetime import datetime, timedelta, timezone

SYNC_WINDOW_HOURS = {
    1: 22,   # Tier 1: daily
    2: 70,   # Tier 2: ~3 days
    3: 166,  # Tier 3: ~7 days
}


def get_sync_cutoff(tier: int = 1) -> datetime:
    """Return the cutoff datetime for sync eligibility.

    Wallets with last_*_sync < cutoff (or NULL) need syncing.
    """
    hours = SYNC_WINDOW_HOURS.get(tier, 166)
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def is_full_sync() -> bool:
    """Return True if FULL_SYNC env var is set (bypasses incremental filter)."""
    return os.environ.get("FULL_SYNC", "").lower() in ("true", "1", "yes")
