"""Compute per-category follow_score for each wallet x category."""

import math
from pandas import DataFrame

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test

# Shared constants synced with app/services/scoring_constants.py
_CAT_EDGE_W = 0.25
_CAT_ROI_PCT_W = 0.25
_CAT_WIN_RATE_W = 0.20
_CAT_SPECIALIST_W = 0.15
_CAT_VOLUME_PCT_W = 0.10
_CAT_RECENCY_W = 0.05
_FOLLOW_THRESHOLD = 0.70
_WATCH_THRESHOLD = 0.35
_SPECIALIST_BONUS = 1.0
_NON_SPECIALIST_BONUS = 0.5
_RECENCY_HALF_LIFE = 90


def compute_category_specialist_bonus(is_specialist: bool) -> float:
    """Specialist bonus: 1.0 if specialist, 0.5 otherwise."""
    return _SPECIALIST_BONUS if is_specialist else _NON_SPECIALIST_BONUS


def get_recommendation(score: float) -> str:
    """Return FOLLOW/WATCH/IGNORE based on score thresholds."""
    if score >= _FOLLOW_THRESHOLD:
        return "FOLLOW"
    elif score >= _WATCH_THRESHOLD:
        return "WATCH"
    else:
        return "IGNORE"


@transformer
def compute_category_follow_scores(data: dict, *args, **kwargs) -> DataFrame:
    """Compute per-category follow_score for each wallet x category.

    Input: dict with 'category_metrics' DataFrame
    Output: DataFrame with per-category follow scores and recommendations
    """
    df = data.get("category_metrics", DataFrame())
    if df.empty:
        print("No category metrics to process")
        return DataFrame(columns=[
            "wallet", "category", "follow_score", "recommendation",
            "roi_percentile", "win_rate", "is_specialist",
            "volume_percentile", "recency_days", "reasons",
            "global_follow_score",
        ])

    def _safe_float(val, default: float = 0.0) -> float:
        """Convert value to float, handling None and NaN."""
        if val is None:
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (TypeError, ValueError):
            return default

    results = []
    for _, row in df.iterrows():
        edge = _safe_float(row.get('global_edge_score'), 0.0)
        roi_percentile = _safe_float(row.get('roi_percentile'), 0.5)
        win_rate = _safe_float(row.get('win_rate'), 0.0)
        is_specialist = bool(row.get('is_specialist', False))
        specialist_bonus = compute_category_specialist_bonus(is_specialist)
        volume_percentile = _safe_float(row.get('volume_percentile'), 0.5)
        recency_days = max(_safe_float(row.get('recency_days'), 999.0), 0)
        recency_score = math.exp(-recency_days / _RECENCY_HALF_LIFE)
        global_follow_score = _safe_float(row.get('global_follow_score'), 0.0)

        follow_score = (
            _CAT_EDGE_W * edge +
            _CAT_ROI_PCT_W * roi_percentile +
            _CAT_WIN_RATE_W * win_rate +
            _CAT_SPECIALIST_W * specialist_bonus +
            _CAT_VOLUME_PCT_W * volume_percentile +
            _CAT_RECENCY_W * recency_score
        )
        follow_score = min(max(follow_score, 0), 1)  # clamp to [0, 1]

        # Generate reasons
        reasons = []
        if roi_percentile > 0.90:
            reasons.append(f"Top 10% ROI in {row['category']}")
        if is_specialist:
            reasons.append(f"{row['category']} specialist ({int(row.get('num_trades', 0))} trades)")
        if win_rate > 0.65:
            reasons.append(f"Win rate {win_rate:.0%} in {row['category']}")
        if edge > 0.50:
            reasons.append(f"Positive global edge ({edge:.2f})")
        num_trades = int(row.get('num_trades', 0))
        if num_trades < 15:
            reasons.append(f"Only {num_trades} trades — limited history")
        if recency_days > 90:
            reasons.append(f"No trades in {row['category']} for {int(recency_days/30)} months")
        if win_rate < 0.40:
            reasons.append(f"Win rate below 40% in {row['category']}")
        if not reasons:
            reasons.append("Insufficient data")

        results.append({
            'wallet': row['wallet'],
            'category': row['category'],
            'follow_score': round(follow_score, 6),
            'recommendation': get_recommendation(follow_score),
            'roi_percentile': round(roi_percentile, 6),
            'win_rate': round(win_rate, 6),
            'is_specialist': is_specialist,
            'volume_percentile': round(volume_percentile, 6) if volume_percentile else None,
            'recency_days': int(recency_days) if recency_days != 999 else None,
            'reasons': reasons,
            'global_follow_score': round(global_follow_score, 6),
        })

    result_df = DataFrame(results)
    print(f"Computed category follow scores for {len(result_df)} wallet x category records")
    return result_df


@test
def test_output(df: DataFrame) -> None:
    assert df is not None, "Output is undefined"
    if not df.empty:
        assert 'wallet' in df.columns, "Missing wallet column"
        assert 'category' in df.columns, "Missing category column"
        assert 'follow_score' in df.columns, "Missing follow_score column"
        assert 'recommendation' in df.columns, "Missing recommendation column"
        assert df['follow_score'].between(0, 1).all(), "Scores must be in [0, 1]"
        valid_recs = {'FOLLOW', 'WATCH', 'IGNORE'}
        assert df['recommendation'].isin(valid_recs).all(), "Invalid recommendation value"
