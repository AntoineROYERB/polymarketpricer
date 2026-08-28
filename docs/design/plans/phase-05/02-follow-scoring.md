# Phase 5 — Follow & Paper Trading — Follow Recommendation Scoring

> **Goal**: Compute a `follow_score` for each wallet that measures how recommendable it is to follow, based on edge, consistency, category expertise, recency, and trade frequency.
> **AI Agent Instructions**: Implement the scoring logic in the service layer (`app/services/follow_scoring.py`) and in the ETL pipeline transformer (`magic/default_repo/transformers/compute_follow_score.py`).

---

## Scoring Formula

```python
follow_score = (
    0.30 * edge_score +
    0.20 * consistency_score +
    0.20 * category_specialization_score +
    0.15 * recency_score +
    0.15 * trade_frequency_score
)
```

### Component Breakdown

| Component | Weight | Source | Description |
|-----------|--------|--------|-------------|
| `edge_score` | 0.30 | `wallet_edge_snapshots.edge_score` | Predictive accuracy (most important) |
| `consistency_score` | 0.20 | `wallet_analytics.consistency_score` | Consistency of returns |
| `category_specialization_score` | 0.20 | `category_analytics` | How many categories the wallet is a specialist in |
| `recency_score` | 0.15 | `wallets.last_seen` | Exponential decay based on days since last trade |
| `trade_frequency_score` | 0.15 | `wallet_analytics.num_trades` | Normalised trades per month |

### Component Details

#### 1. Edge Score (0.30)
Directly use `wallet_edge_snapshots.edge_score` (already normalised to [0, 1] in Phase 4). If NULL → 0.

#### 2. Consistency Score (0.20)
Use `wallet_analytics.consistency_score` (already computed in Phase 1, range [0, 1]). If NULL → 0.

#### 3. Category Specialization Score (0.20)
```python
def compute_category_specialization(wallet: str) -> float:
    """
    Score based on:
    - Number of categories where wallet is a specialist (is_specialist = True)
    - Category ranks (lower rank = better)
    - Normalised to [0, 1], max 8 categories
    """
    query = """
        SELECT COUNT(*) as specialist_count,
               AVG(category_rank) as avg_rank
        FROM category_analytics
        WHERE wallet = :wallet
          AND is_specialist = true
          AND snapshot_date = CURRENT_DATE
    """
    result = execute(query)
    specialist_count = result.specialist_count or 0
    avg_rank = result.avg_rank or 50  # default middle rank

    # Score: 0.5 * (specialists / 8) + 0.5 * (1 - avg_rank / 100)
    score = 0.5 * min(specialist_count / 8, 1) + 0.5 * max(1 - avg_rank / 100, 0)
    return score
```

#### 4. Recency Score (0.15)
```python
def compute_recency_score(wallet: str) -> float:
    """
    Exponential decay based on days since last trade.
    Score = e^(-days_since_last_trade / 90)
    - Trade today → score = 1.0
    - Trade 30 days ago → score = 0.72
    - Trade 90 days ago → score = 0.37
    - Trade 365 days ago → score = 0.02
    """
    query = """
        SELECT EXTRACT(DAY FROM (CURRENT_DATE - MAX(timestamp::date))) as days_since
        FROM trades WHERE wallet = :wallet
    """
    result = execute(query)
    days_since = result.days_since or 999
    return math.exp(-days_since / 90)
```

#### 5. Trade Frequency Score (0.15)
```python
def compute_trade_frequency_score(wallet: str) -> float:
    """
    Trades per month, normalised with sigmoid.
    Score = 1 / (1 + e^(-0.1 * (trades_per_month - 10)))
    - 0 trades/mo → 0.27
    - 10 trades/mo → 0.50
    - 30 trades/mo → 0.88
    - 50 trades/mo → 0.98
    """
    query = """
        SELECT COUNT(*) as total_trades,
               EXTRACT(DAY FROM (CURRENT_DATE - MIN(timestamp::date))) / 30.0 as months_active
        FROM trades WHERE wallet = :wallet
    """
    result = execute(query)
    total_trades = result.total_trades or 0
    months_active = max(result.months_active or 1, 1)
    trades_per_month = total_trades / months_active
    return 1 / (1 + math.exp(-0.1 * (trades_per_month - 10)))
```

---

## Normalisation

The `follow_score` is automatically in [0, 1] range because:
- `edge_score` is already [0, 1]
- `consistency_score` is already [0, 1]
- `category_specialization_score` is computed to be [0, 1]
- `recency_score` is [0, 1] (exponential decay)
- `trade_frequency_score` is [0, 1] (sigmoid)
- Final score = weighted sum, also [0, 1]

**No min-max normalisation needed** — unlike the wallet_score which uses min-max across the cohort, follow_score per-wallet is self-contained.

---

## Per-Category Follow Scoring

Each wallet can have a different follow_score per category. This answers "should I follow this trader in Politics specifically?"

### Formula

```python
category_follow_score = (
    0.25 * edge_score +                    # global edge (from wallet_edge_snapshots)
    0.25 * category_roi_percentile +        # ROI percentile within this category
    0.20 * category_win_rate +              # win rate in this category
    0.15 * specialist_bonus +               # 1.0 if specialist, 0.5 otherwise
    0.10 * category_volume_percentile +     # volume percentile in this category
    0.05 * category_recency_score           # recency in this category
)
```

### Component Breakdown

| Component | Weight | Source | Description |
|-----------|--------|--------|-------------|
| `edge_score` | 0.25 | `wallet_edge_snapshots.edge_score` | Global predictive accuracy |
| `category_roi_percentile` | 0.25 | `category_analytics.roi` | ROI percentile across all wallets in this category |
| `category_win_rate` | 0.20 | `category_analytics.win_rate` | Win rate in this category (already [0,1]) |
| `specialist_bonus` | 0.15 | `category_analytics.is_specialist` | 1.0 if is_specialist, 0.5 otherwise |
| `category_volume_percentile` | 0.10 | `category_analytics.total_volume` | Volume percentile in this category |
| `category_recency_score` | 0.05 | `trades` filtered by category | Exponential decay, e^(-days_since_last_category_trade / 90) |

### Recommendation Thresholds

| Score Range | Recommendation |
|-------------|---------------|
| ≥ 0.70 | `FOLLOW` — Strong performer in this category |
| ≥ 0.35 | `WATCH` — Decent but needs more data |
| < 0.35 | `IGNORE` — Weak or insufficient activity |

### Category Recency Score

```python
def compute_category_recency_score(wallet: str, category: str) -> float:
    """
    Exponential decay based on days since last trade in this category.
    Falls back to global recency if no category-specific trades exist.
    """
    query = """
        SELECT EXTRACT(DAY FROM (CURRENT_DATE - MAX(t.timestamp::date))) as days_since
        FROM trades t
        JOIN markets m ON m.id = t.market_id
        WHERE t.wallet = :wallet
          AND (m.mapped_category = :category OR m.category = :category)
    """
    result = execute(query, {"wallet": wallet, "category": category})
    days_since = result.days_since or 999
    return math.exp(-days_since / 90)
```

### Reason Generation (per-category)

For each wallet + category, generate top 2-3 reasons:

| Condition | Reason |
|-----------|--------|
| `roi_percentile > 0.90` | `"Top 10% ROI in {category}"` |
| `is_specialist = true` | `"{category} specialist ({num_trades} trades)"` |
| `win_rate > 0.65` | `"Win rate {win_rate:.0%} in {category}"` |
| `edge_score > 0.50` | `"Positive global edge ({edge_score:.2f})"` |
| `num_trades < 15` | `"Only {num_trades} trades — limited history"` |
| `recency_days > 90` | `"No trades in {category} for {months} months"` |
| `win_rate < 0.40` | `"Win rate below 40% in {category}"` |

### Aggregation to Global Score

The global `follow_score` on `wallet_analytics` remains the original formula (edge + consistency + specialization + recency + frequency). The per-category scores are stored separately in `wallet_category_follow_scores` and as a JSONB summary in `wallet_analytics.category_follow_scores`.

```python
category_follow_scores_json = {
    "politics": {"follow_score": 0.92, "recommendation": "FOLLOW"},
    "crypto": {"follow_score": 0.45, "recommendation": "WATCH"},
    "sports": {"follow_score": 0.12, "recommendation": "IGNORE"},
}
```

---

## Service Layer: `app/services/follow_scoring.py`

```python
"""Follow recommendation scoring service."""

import math
from decimal import Decimal
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def compute_follow_score(
    db: AsyncSession, wallet: str
) -> tuple[Decimal, list[str]]:
    """Compute follow_score for a single wallet. Returns (score, reasons)."""
    reasons = []

    # 1. Edge score
    edge = await _get_edge_score(db, wallet)
    if edge and edge > 0:
        reasons.append(f"Edge score: {edge:.2f}")

    # 2. Consistency score
    consistency = await _get_consistency_score(db, wallet)
    if consistency and consistency > 0:
        reasons.append(f"Consistency: {consistency:.2f}")

    # 3. Category specialization
    spec_score, spec_details = await _get_category_specialization(db, wallet)
    if spec_details:
        reasons.append(f"Specialist in {spec_details}")

    # 4. Recency score
    recency = await _get_recency_score(db, wallet)

    # 5. Trade frequency score
    frequency = await _get_trade_frequency_score(db, wallet)

    # Compute weighted score
    score = (
        Decimal("0.30") * (edge or Decimal("0")) +
        Decimal("0.20") * (consistency or Decimal("0")) +
        Decimal("0.20") * (spec_score or Decimal("0")) +
        Decimal("0.15") * (recency or Decimal("0")) +
        Decimal("0.15") * (frequency or Decimal("0"))
    )

    if not reasons:
        reasons.append("Insufficient data")

    return score, reasons


async def get_follow_recommendations(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> list[dict]:
    """Return top-N wallets by follow_score."""
    query = text("""
        SELECT wallet, follow_score
        FROM wallet_analytics
        WHERE follow_score IS NOT NULL
          AND snapshot_date = CURRENT_DATE
        ORDER BY follow_score DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(query, {"limit": limit, "offset": offset})
    rows = result.all()

    recommendations = []
    for row in rows:
        score, reasons = await compute_follow_score(db, row.wallet)
        recommendations.append({
            "wallet": row.wallet,
            "follow_score": row.follow_score,
            "reasons": reasons,
        })
    return recommendations
```

---

### Extended Service Layer

Add to `app/services/follow_scoring.py`:

```python
async def compute_category_follow_score(
    db: AsyncSession, wallet: str, category: str
) -> tuple[Decimal, str, list[str]]:
    """Compute per-category follow_score. Returns (score, recommendation, reasons)."""
    reasons = []

    # 1. Get global edge score
    edge = await _get_edge_score(db, wallet)

    # 2. Get category-specific analytics
    cat_result = await db.execute(
        text("""
            SELECT roi, win_rate, num_trades, total_volume, is_specialist
            FROM category_analytics
            WHERE wallet = :wallet AND category = :category
            ORDER BY snapshot_date DESC
            LIMIT 1
        """),
        {"wallet": wallet, "category": category},
    )
    cat_row = cat_result.one_or_none()

    if cat_row is None or (cat_row.num_trades or 0) == 0:
        return Decimal("0"), "IGNORE", ["No activity in this category"]

    # 3. Compute percentiles within category
    roi = float(cat_row.roi or 0)
    volume = float(cat_row.total_volume or 0)

    percentile_result = await db.execute(
        text("""
            SELECT
                PERCENT_RANK() OVER (ORDER BY roi DESC) as roi_percentile,
                PERCENT_RANK() OVER (ORDER BY total_volume DESC) as vol_percentile
            FROM category_analytics
            WHERE category = :category AND snapshot_date = CURRENT_DATE
            AND wallet = :wallet
        """),
        {"category": category, "wallet": wallet},
    )
    p_row = percentile_result.one_or_none()
    roi_percentile = float(p_row.roi_percentile) if p_row else 0.5

    # 4. Win rate
    win_rate = float(cat_row.win_rate or 0)

    # 5. Specialist bonus
    is_specialist = bool(cat_row.is_specialist)
    specialist_bonus = 1.0 if is_specialist else 0.5

    # 6. Category recency
    recency = await _get_category_recency(db, wallet, category)

    # 7. Compute score
    score = (
        Decimal("0.25") * (edge or Decimal("0")) +
        Decimal("0.25") * Decimal(str(roi_percentile)) +
        Decimal("0.20") * Decimal(str(win_rate)) +
        Decimal("0.15") * Decimal(str(specialist_bonus)) +
        Decimal("0.10") * Decimal("0.5") +  # placeholder for volume_percentile
        Decimal("0.05") * (recency or Decimal("0"))
    )

    # 8. Generate reasons
    if roi_percentile > 0.90:
        reasons.append(f"Top 10% ROI in {category}")
    if is_specialist:
        reasons.append(f"{category} specialist ({cat_row.num_trades} trades)")
    if win_rate > 0.65:
        reasons.append(f"Win rate {win_rate:.0%} in {category}")
    if edge and edge > 0.50:
        reasons.append(f"Positive global edge ({edge:.2f})")
    if cat_row.num_trades and cat_row.num_trades < 15:
        reasons.append(f"Only {cat_row.num_trades} trades — limited history")

    # 9. Recommendation
    recommendation = "FOLLOW" if score >= Decimal("0.70") else \
                     "WATCH" if score >= Decimal("0.35") else \
                     "IGNORE"

    return score, recommendation, reasons


async def get_category_follow_leaderboard(
    db: AsyncSession, category: str, limit: int = 20, offset: int = 0
) -> list[dict]:
    """Top-N wallets by follow_score in a specific category."""
    query = text("""
        SELECT wallet, follow_score, recommendation,
               roi_percentile, win_rate, is_specialist, reasons
        FROM wallet_category_follow_scores
        WHERE category = :category
          AND snapshot_date = CURRENT_DATE
        ORDER BY follow_score DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(query, {"category": category, "limit": limit, "offset": offset})
    return [dict(row._mapping) for row in result.all()]


async def get_wallet_category_scores(
    db: AsyncSession, wallet: str
) -> list[dict]:
    """All category follow scores for a wallet."""
    query = text("""
        SELECT * FROM wallet_category_follow_scores
        WHERE wallet = :wallet
          AND snapshot_date = CURRENT_DATE
        ORDER BY follow_score DESC
    """)
    result = await db.execute(query, {"wallet": wallet})
    return [dict(row._mapping) for row in result.all()]
```


## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `app/services/follow_scoring.py` — global + per-category scoring |
| EDIT | `app/api/v1/follow.py` — uses `get_follow_recommendations` + `get_category_follow_leaderboard` + `get_wallet_category_scores` |

---

## Verification

```python
# Test edge cases for global follow_score:
# - Wallet with no edge data → follow_score = 0.20*consistency + ...
# - Wallet with perfect scores → follow_score = 1.0
# - Wallet inactive for 2 years → recency_score ≈ 0
# - Wallet with 1 trade ever → frequency_score ≈ 0.27

# Test edge cases for per-category follow_score:
# - Wallet with no activity in category → score = 0, IGNORE
# - Wallet with perfect scores in category → score = 1.0, FOLLOW
# - Wallet with roi_percentile = 0.95 → reason "Top 5% ROI in {category}"
# - Wallet with is_specialist = false → specialist_bonus = 0.5
# - Wallet with 5 trades in category → reason "limited history"
```
