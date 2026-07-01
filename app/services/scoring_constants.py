"""Shared constants for follow scoring formulas.

All scoring weights, thresholds, and parameters are defined here
to avoid drift between the service layer (async SQLAlchemy),
ETL layer (Mage AI pandas), and test layer.
"""

from decimal import Decimal

# ── Global follow scoring weights ──────────────────────────────────
# Formula: EDGE * edge_score + CONSISTENCY * consistency_score
#          + SPECIALIZATION * specialization_score
#          + RECENCY * recency_score + FREQUENCY * frequency_score
EDGE_WEIGHT = Decimal("0.30")
CONSISTENCY_WEIGHT = Decimal("0.20")
SPECIALIZATION_WEIGHT = Decimal("0.20")
RECENCY_WEIGHT = Decimal("0.15")
FREQUENCY_WEIGHT = Decimal("0.15")

# Float versions for ETL (pandas) and tests
EDGE_WEIGHT_F = 0.30
CONSISTENCY_WEIGHT_F = 0.20
SPECIALIZATION_WEIGHT_F = 0.20
RECENCY_WEIGHT_F = 0.15
FREQUENCY_WEIGHT_F = 0.15

# ── Per-category follow scoring weights ────────────────────────────
# Formula: CAT_EDGE * edge + CAT_ROI_PCT * roi_percentile
#          + CAT_WIN_RATE * win_rate + CAT_SPECIALIST * specialist_bonus
#          + CAT_VOLUME_PCT * volume_percentile + CAT_RECENCY * recency
CAT_EDGE_WEIGHT = Decimal("0.25")
CAT_ROI_PERCENTILE_WEIGHT = Decimal("0.25")
CAT_WIN_RATE_WEIGHT = Decimal("0.20")
CAT_SPECIALIST_BONUS_WEIGHT = Decimal("0.15")
CAT_VOLUME_PERCENTILE_WEIGHT = Decimal("0.10")
CAT_RECENCY_WEIGHT = Decimal("0.05")

CAT_EDGE_WEIGHT_F = 0.25
CAT_ROI_PERCENTILE_WEIGHT_F = 0.25
CAT_WIN_RATE_WEIGHT_F = 0.20
CAT_SPECIALIST_BONUS_WEIGHT_F = 0.15
CAT_VOLUME_PERCENTILE_WEIGHT_F = 0.10
CAT_RECENCY_WEIGHT_F = 0.05

# ── Recommendation thresholds ──────────────────────────────────────
FOLLOW_THRESHOLD = Decimal("0.70")
WATCH_THRESHOLD = Decimal("0.35")

FOLLOW_THRESHOLD_F = 0.70
WATCH_THRESHOLD_F = 0.35

# ── Specialist bonus ───────────────────────────────────────────────
SPECIALIST_BONUS = Decimal("1.0")
NON_SPECIALIST_BONUS = Decimal("0.5")

SPECIALIST_BONUS_F = 1.0
NON_SPECIALIST_BONUS_F = 0.5

# ── Category specialization parameters ─────────────────────────────
MAX_SPECIALIST_CATEGORIES = 8

# ── Recency decay ──────────────────────────────────────────────────
RECENCY_HALF_LIFE_DAYS = 90  # e^(-days / 90)

# ── Trade frequency sigmoid ────────────────────────────────────────
FREQ_SLOPE = 0.1     # sigmoid steepness
FREQ_MIDPOINT = 10   # trades-per-month at sigmoid midpoint


def get_recommendation(score: Decimal) -> str:
    """Return FOLLOW / WATCH / IGNORE based on score thresholds."""
    if score >= FOLLOW_THRESHOLD:
        return "FOLLOW"
    if score >= WATCH_THRESHOLD:
        return "WATCH"
    return "IGNORE"


def get_recommendation_f(score: float) -> str:
    """Float version for ETL and tests."""
    if score >= FOLLOW_THRESHOLD_F:
        return "FOLLOW"
    if score >= WATCH_THRESHOLD_F:
        return "WATCH"
    return "IGNORE"
