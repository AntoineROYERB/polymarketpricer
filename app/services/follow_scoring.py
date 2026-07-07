"""Follow recommendation scoring service."""

import math
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scoring_constants import (
    EDGE_WEIGHT,
    CONSISTENCY_WEIGHT,
    SPECIALIZATION_WEIGHT,
    RECENCY_WEIGHT,
    FREQUENCY_WEIGHT,
    CAT_EDGE_WEIGHT,
    CAT_ROI_PERCENTILE_WEIGHT,
    CAT_WIN_RATE_WEIGHT,
    CAT_SPECIALIST_BONUS_WEIGHT,
    CAT_VOLUME_PERCENTILE_WEIGHT,
    CAT_RECENCY_WEIGHT,
    SPECIALIST_BONUS,
    NON_SPECIALIST_BONUS,
    MAX_SPECIALIST_CATEGORIES,
    RECENCY_HALF_LIFE_DAYS,
    FREQ_SLOPE,
    FREQ_MIDPOINT,
    get_recommendation,
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
        EDGE_WEIGHT * (edge or Decimal("0"))
        + CONSISTENCY_WEIGHT * (consistency or Decimal("0"))
        + SPECIALIZATION_WEIGHT * (spec_score or Decimal("0"))
        + RECENCY_WEIGHT * (recency or Decimal("0"))
        + FREQUENCY_WEIGHT * (frequency or Decimal("0"))
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
        score, reasons = await compute_follow_score(db, row._mapping["wallet"])
        recommendations.append({
            "wallet": row._mapping["wallet"],
            "follow_score": row._mapping["follow_score"],
            "reasons": reasons,
        })
    return recommendations


async def compute_category_follow_score(
    db: AsyncSession, wallet: str, category: str
) -> tuple[Decimal, str, list[str]]:
    """Compute per-category follow_score. Returns (score, recommendation, reasons)."""
    reasons = []

    edge = await _get_edge_score(db, wallet)

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

    if cat_row is None or (cat_row._mapping["num_trades"] or 0) == 0:
        return Decimal("0"), "IGNORE", ["No activity in this category"]

    win_rate = Decimal(str(cat_row._mapping["win_rate"] or 0))
    num_trades = int(cat_row._mapping["num_trades"] or 0)
    is_specialist = bool(cat_row._mapping["is_specialist"])

    # Compute ROI percentile across ALL wallets in this category
    percentile_result = await db.execute(
        text("""
            SELECT wallet,
                   PERCENT_RANK() OVER (ORDER BY roi DESC) as percentile
            FROM category_analytics
            WHERE category = :category
              AND snapshot_date = (SELECT MAX(snapshot_date) FROM category_analytics)
        """),
        {"category": category},
    )
    all_rows = percentile_result.all()
    roi_percentile = Decimal("0.5")
    for r in all_rows:
        if r._mapping["wallet"] == wallet:
            roi_percentile = Decimal(str(r._mapping["percentile"]))
            break

    # Compute volume percentile across ALL wallets in this category
    volume_percentile = await _get_volume_percentile(db, wallet, category)

    specialist_bonus = SPECIALIST_BONUS if is_specialist else NON_SPECIALIST_BONUS
    recency = await _get_category_recency(db, wallet, category)

    score = (
        CAT_EDGE_WEIGHT * (edge or Decimal("0"))
        + CAT_ROI_PERCENTILE_WEIGHT * Decimal(str(roi_percentile))
        + CAT_WIN_RATE_WEIGHT * win_rate
        + CAT_SPECIALIST_BONUS_WEIGHT * specialist_bonus
        + CAT_VOLUME_PERCENTILE_WEIGHT * (volume_percentile or Decimal("0"))
        + CAT_RECENCY_WEIGHT * (recency or Decimal("0"))
    )
    score = max(Decimal("0"), min(Decimal("1"), score))

    if roi_percentile > Decimal("0.90"):
        reasons.append(f"Top 10% ROI in {category}")
    if is_specialist:
        reasons.append(f"{category} specialist ({num_trades} trades)")
    if win_rate > 0.65:
        reasons.append(f"Win rate {win_rate:.0%} in {category}")
    if edge and edge > Decimal("0.50"):
        reasons.append(f"Positive global edge ({edge:.2f})")
    if num_trades < 15:
        reasons.append(f"Only {num_trades} trades — limited history")

    recommendation = get_recommendation(score)

    return score, recommendation, reasons


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


async def _get_edge_score(db: AsyncSession, wallet: str) -> Optional[Decimal]:
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


async def _get_consistency_score(db: AsyncSession, wallet: str) -> Optional[Decimal]:
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
        return Decimal("0"), ""

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
        return Decimal("0")

    total_trades = float(row._mapping["total_trades"] or 0)
    months_active = max(float(row._mapping["months_active"] or 1), 1)
    trades_per_month = total_trades / months_active if months_active > 0 else 0
    score = 1 / (1 + math.exp(-FREQ_SLOPE * (trades_per_month - FREQ_MIDPOINT)))
    return Decimal(str(round(score, 6)))


async def _get_volume_percentile(db: AsyncSession, wallet: str, category: str) -> Decimal:
    """Compute volume percentile for a wallet within a category."""
    result = await db.execute(
        text("""
            SELECT percentile
            FROM (
                SELECT wallet,
                       PERCENT_RANK() OVER (ORDER BY total_volume DESC) as percentile
                FROM category_analytics
                WHERE category = :category
                  AND snapshot_date = (SELECT MAX(snapshot_date) FROM category_analytics)
            ) sub
            WHERE sub.wallet = :wallet
        """),
        {"category": category, "wallet": wallet},
    )
    row = result.one_or_none()
    return Decimal(str(row._mapping["percentile"])) if row else Decimal("0.5")


async def _get_category_recency(db: AsyncSession, wallet: str, category: str) -> Decimal:
    result = await db.execute(
        text("""
            SELECT (CURRENT_DATE - MAX(t.timestamp::date)) as days_since
            FROM trades t
            JOIN markets m ON m.id = t.market_id
            WHERE t.wallet = :wallet
              AND (m.mapped_category = :category OR m.category = :category)
        """),
        {"wallet": wallet, "category": category},
    )
    row = result.one_or_none()
    days_since = float(row._mapping["days_since"]) if row and row._mapping.get("days_since") else 999
    score = math.exp(-days_since / RECENCY_HALF_LIFE_DAYS)
    return Decimal(str(round(score, 6)))
