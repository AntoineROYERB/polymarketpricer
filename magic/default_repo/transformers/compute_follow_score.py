"""Compute global follow_score for each wallet."""

import math
from pandas import DataFrame

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

# Import shared constants (note: this runs inside Mage AI container;
# the app package must be on the PYTHONPATH or these are inlined).
# For portability, we inline the constants here but keep them synced
# with app/services/scoring_constants.py.
_EDGE_W = 0.30
_CONSISTENCY_W = 0.20
_SPECIALIZATION_W = 0.20
_RECENCY_W = 0.15
_FREQUENCY_W = 0.15
_MAX_SPECIALIST_CATS = 8
_RECENCY_HALF_LIFE = 90
_FREQ_SLOPE = 0.1
_FREQ_MIDPOINT = 10


def compute_category_specialization(row: dict) -> float:
    """Score based on specialist count and avg rank.

    Score = 0.5 * (specialists / MAX_SPECIALIST_CATS) + 0.5 * (1 - avg_rank / 100)
    """
    specialist_count = float(row.get('specialist_count', 0))
    avg_rank = float(row.get('avg_category_rank', 50))
    spec_part = 0.5 * min(specialist_count / _MAX_SPECIALIST_CATS, 1)
    rank_part = 0.5 * max(1 - avg_rank / 100, 0)
    return spec_part + rank_part


def compute_recency_score(days_since: float) -> float:
    """Exponential decay. Score = e^(-days / RECENCY_HALF_LIFE)."""
    return math.exp(-days_since / _RECENCY_HALF_LIFE)


def compute_frequency_score(total_trades: float, months_active: float) -> float:
    """Sigmoid normalisation. Score = 1/(1+e^(-SLOPE*(tpm-MIDPOINT)))."""
    tpm = total_trades / max(months_active, 1)
    return 1 / (1 + math.exp(-_FREQ_SLOPE * (tpm - _FREQ_MIDPOINT)))


@transformer
def compute_follow_score(data: dict, *args, **kwargs) -> DataFrame:
    """Compute follow_score for each wallet.

    Input: dict with 'global_metrics' DataFrame
    Output: DataFrame with wallet and follow_score columns
    """
    df = data.get("global_metrics", DataFrame())
    if df.empty:
        print("No global metrics to process")
        return DataFrame(columns=["wallet", "follow_score"])

    results = []
    for _, row in df.iterrows():
        edge = float(row.get('edge_score', 0))
        consistency = float(row.get('consistency_score', 0))
        spec_score = compute_category_specialization(row)
        recency = compute_recency_score(float(row.get('days_since_last_trade', 999)))
        frequency = compute_frequency_score(
            float(row.get('total_trades', 0)),
            float(row.get('months_active', 1)),
        )

        follow_score = (
            _EDGE_W * edge +
            _CONSISTENCY_W * consistency +
            _SPECIALIZATION_W * spec_score +
            _RECENCY_W * recency +
            _FREQUENCY_W * frequency
        )

        results.append({
            'wallet': row['wallet'],
            'follow_score': round(follow_score, 6),
        })

    result_df = DataFrame(results)
    print(f"Computed follow_score for {len(result_df)} wallets")
    return result_df


@test
def test_output(df: DataFrame) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert 'wallet' in df.columns, "Missing wallet column"
        assert 'follow_score' in df.columns, "Missing follow_score column"
        assert df['follow_score'].between(0, 1).all(), "Scores must be in [0, 1]"
