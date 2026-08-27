"""Follow recommendation scoring service."""

import math
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scoring_constants import (
    CONSISTENCY_WEIGHT,
    EDGE_WEIGHT,
    FREQ_MIDPOINT,
    FREQ_SLOPE,
    FREQUENCY_WEIGHT,
    MAX_SPECIALIST_CATEGORIES,
    RECENCY_HALF_LIFE_DAYS,
    RECENCY_WEIGHT,
    SPECIALIZATION_WEIGHT,
)


async def compute_follow_score(
    db: AsyncSession, wallet: str
) -> tuple[Decimal, list[str]]:
    """Compute follow_score for a single wallet. Returns (score, reasons)."""
    reasons = []

    edge = await _get_edge_score(db, wallet)
    if edge and edge > 0:
        reasons.append(f"Edge score: {edge:.2f}")

    consistency = await _get_consistency_score(db, wallet)
    if consistency and consistency > 0:
        reasons.append(f"Consistency: {consistency:.2f}")

    spec_score, spec_details = await _get_category_specialization(db, wallet)
    if spec_details:
        reasons.append(f"Specialist in {spec_details}")

    recency = await _get_recency_score(db, wallet)
    frequency = await _get_trade_frequency_score(db, wallet)

    score = (
        EDGE_WEIGHT * (edge or Decimal(0))
        + CONSISTENCY_WEIGHT * (consistency or Decimal(0))
        + SPECIALIZATION_WEIGHT * (spec_score or Decimal(0))
        + RECENCY_WEIGHT * (recency or Decimal(0))
        + FREQUENCY_WEIGHT * (frequency or Decimal(0))
    )

    if not reasons:
        reasons.append("Insufficient data")

    return score, reasons


async def get_follow_recommendations(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    """Return top-N wallets by follow_score."""
    query = text("""
        SELECT wallet, follow_score
        FROM wallet_analytics
        WHERE follow_score IS NOT NULL
          AND snapshot_date = (SELECT MAX(snapshot_date) FROM wallet_analytics)
        ORDER BY follow_score DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(query, {"limit": limit, "offset": offset})
    rows = result.all()

    recommendations = []
    for row in rows:
        _score, reasons = await compute_follow_score(db, row._mapping["wallet"])
        recommendations.append({
            "wallet": row._mapping["wallet"],
            "follow_score": row._mapping["follow_score"],
            "reasons": reasons,
        })
    return recommendations


async def get_category_follow_leaderboard(
    db: AsyncSession, category: str, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    """Top-N wallets by follow_score in a specific category."""
    query = text("""
        SELECT wallet, follow_score, recommendation,
               roi_percentile, win_rate, is_specialist, reasons
        FROM wallet_category_follow_scores
        WHERE category = :category
          AND snapshot_date = (SELECT MAX(snapshot_date) FROM wallet_category_follow_scores)
        ORDER BY follow_score DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(query, {"category": category, "limit": limit, "offset": offset})
    return [dict(row._mapping) for row in result.all()]


async def get_wallet_category_scores(
    db: AsyncSession, wallet: str
) -> list[dict[str, Any]]:
    """All category follow scores for a wallet."""
    query = text("""
        SELECT * FROM wallet_category_follow_scores
        WHERE wallet = :wallet
          AND snapshot_date = (SELECT MAX(snapshot_date) FROM wallet_category_follow_scores)
        ORDER BY follow_score DESC
    """)
    result = await db.execute(query, {"wallet": wallet})
    return [dict(row._mapping) for row in result.all()]


async def _get_edge_score(db: AsyncSession, wallet: str) -> Decimal | None:
    result = await db.execute(
        text("""
            SELECT edge_score FROM wallet_edge_snapshots
            WHERE wallet = :wallet
            ORDER BY snapshot_date DESC
            LIMIT 1
        """),
        {"wallet": wallet},
    )
    row = result.one_or_none()
    if row and row._mapping.get("edge_score") is not None:
        return Decimal(str(row._mapping["edge_score"]))
    return None


async def _get_consistency_score(db: AsyncSession, wallet: str) -> Decimal | None:
    result = await db.execute(
        text("""
            SELECT consistency_score FROM wallet_analytics
            WHERE wallet = :wallet
              AND snapshot_date = (SELECT MAX(snapshot_date) FROM wallet_analytics)
        """),
        {"wallet": wallet},
    )
    row = result.one_or_none()
    if row and row._mapping.get("consistency_score") is not None:
        return Decimal(str(row._mapping["consistency_score"]))
    return None


async def _get_category_specialization(
    db: AsyncSession, wallet: str
) -> tuple[Decimal, str]:
    result = await db.execute(
        text("""
            SELECT COUNT(*) as specialist_count,
                   AVG(category_rank) as avg_rank
            FROM category_analytics
            WHERE wallet = :wallet
              AND is_specialist = true
              AND snapshot_date = (SELECT MAX(snapshot_date) FROM category_analytics)
        """),
        {"wallet": wallet},
    )
    row = result.one_or_none()
    if not row:
        return Decimal(0), ""

    specialist_count = int(row._mapping["specialist_count"] or 0)
    avg_rank = float(row._mapping["avg_rank"] or 50)

    score = 0.5 * min(specialist_count / MAX_SPECIALIST_CATEGORIES, 1) + 0.5 * max(1 - avg_rank / 100, 0)
    details = ""
    if specialist_count > 0:
        details = f"{specialist_count} categories"

    return Decimal(str(round(score, 6))), details


async def _get_recency_score(db: AsyncSession, wallet: str) -> Decimal:
    result = await db.execute(
        text("""
            SELECT (CURRENT_DATE - MAX(timestamp::date)) as days_since
            FROM trades WHERE wallet = :wallet
        """),
        {"wallet": wallet},
    )
    row = result.one_or_none()
    days_since = float(row._mapping["days_since"]) if row and row._mapping.get("days_since") else 999
    score = math.exp(-days_since / RECENCY_HALF_LIFE_DAYS)
    return Decimal(str(round(score, 6)))


async def _get_trade_frequency_score(db: AsyncSession, wallet: str) -> Decimal:
    result = await db.execute(
        text("""
            SELECT COUNT(*) as total_trades,
                   (CURRENT_DATE - MIN(timestamp::date)) / 30.0 as months_active
            FROM trades WHERE wallet = :wallet
        """),
        {"wallet": wallet},
    )
    row = result.one_or_none()
    if not row:
        return Decimal(0)

    total_trades = float(row._mapping["total_trades"] or 0)
    months_active = max(float(row._mapping["months_active"] or 1), 1)
    trades_per_month = total_trades / months_active if months_active > 0 else 0
    score = 1 / (1 + math.exp(-FREQ_SLOPE * (trades_per_month - FREQ_MIDPOINT)))
    return Decimal(str(round(score, 6)))



