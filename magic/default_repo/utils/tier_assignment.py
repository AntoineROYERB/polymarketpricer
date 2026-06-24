"""Assign wallet tiers based on analytics scores."""


def assign_tier(
    wallet_score: float | None,
    num_trades: int | None,
    total_volume: float | None,
    days_since_first_seen: int | None,
) -> int:
    """Assign a wallet to tier 1, 2, or 3 based on quality signals.

    Tier 1 (daily sync): elite traders with high scores or volume.
    Tier 2 (every 3 days): intermediate traders.
    Tier 3 (weekly): long tail / default.
    """
    score = wallet_score or 0
    trades = num_trades or 0
    volume = total_volume or 0
    age = days_since_first_seen or 0

    # Tier 1: smart money wallets
    if score >= 80:
        return 1
    if trades >= 500 and score >= 60:
        return 1
    if volume >= 500_000 and score >= 50:
        return 1

    # Tier 2: intermediate wallets
    if score >= 50:
        return 2
    if trades >= 200 and score >= 40:
        return 2
    if volume >= 50_000 and age >= 30:
        return 2

    # Tier 3: long tail
    return 3
