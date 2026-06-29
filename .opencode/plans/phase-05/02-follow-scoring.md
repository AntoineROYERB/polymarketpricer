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

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `app/services/follow_scoring.py` |
| EDIT | `app/api/v1/follow.py` — uses `get_follow_recommendations` for `/recommendations` |

---

## Verification

```python
# Test edge cases:
# - Wallet with no edge data → follow_score = 0.20*consistency + ...
# - Wallet with perfect scores → follow_score = 1.0
# - Wallet inactive for 2 years → recency_score ≈ 0
# - Wallet with 1 trade ever → frequency_score ≈ 0.27
```
