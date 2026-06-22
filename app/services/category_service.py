from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

"""Category analytics service layer.

Provides queries for category leaderboards, wallet category breakdowns,
and category detail views against the category_analytics and
category_rankings tables.
"""

from app.db.models import Category, CategoryAnalytic, CategoryRanking, Wallet


async def get_categories(
    db: AsyncSession,
) -> list[str]:
    stmt = (
        select(Category.category)
        .order_by(Category.label)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_category_labels(
    db: AsyncSession,
) -> list[Category]:
    stmt = (
        select(Category)
        .order_by(Category.label)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_wallet_categories(
    db: AsyncSession,
    address: str,
) -> list[CategoryAnalytic]:
    latest_per_category = (
        select(
            CategoryAnalytic.category,
            CategoryAnalytic.snapshot_date,
        )
        .where(CategoryAnalytic.wallet == address)
        .order_by(
            CategoryAnalytic.category,
            CategoryAnalytic.snapshot_date.desc(),
        )
        .distinct(CategoryAnalytic.category)
        .subquery()
    )

    stmt = (
        select(CategoryAnalytic)
        .join(
            latest_per_category,
            (CategoryAnalytic.category == latest_per_category.c.category)
            & (CategoryAnalytic.snapshot_date == latest_per_category.c.snapshot_date),
        )
        .where(CategoryAnalytic.wallet == address)
        .order_by(CategoryAnalytic.category)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_category_leaderboard(
    db: AsyncSession,
    category: str,
    list_type: str = "top_50",
    limit: int = 50,
    offset: int = 0,
) -> list[CategoryRanking]:
    stmt = (
        select(CategoryRanking)
        .where(CategoryRanking.category == category)
        .where(CategoryRanking.list_type == list_type)
        .order_by(CategoryRanking.rank.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_wallet_category_detail(
    db: AsyncSession,
    address: str,
    category: str,
) -> Optional[CategoryAnalytic]:
    stmt = (
        select(CategoryAnalytic)
        .where(
            CategoryAnalytic.wallet == address,
            CategoryAnalytic.category == category,
        )
        .order_by(CategoryAnalytic.snapshot_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def wallet_exists(
    db: AsyncSession,
    address: str,
) -> bool:
    stmt = select(Wallet.wallet).where(Wallet.wallet == address)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


def _to_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    return Decimal(str(val))


def ranking_to_leaderboard_entry(
    row: CategoryRanking,
    is_specialist: bool = False,
) -> dict[str, Any]:
    return {
        "rank": row.rank,
        "wallet": row.wallet,
        "wallet_score": _to_decimal(row.wallet_score),
        "roi": _to_decimal(row.roi),
        "win_rate": _to_decimal(row.win_rate),
        "total_pnl": _to_decimal(row.total_pnl),
        "num_trades": row.num_trades or 0,
        "total_volume": _to_decimal(row.total_volume),
        "is_specialist": is_specialist,
    }


def analytic_to_category_summary(
    row: CategoryAnalytic,
) -> dict[str, Any]:
    return {
        "category": row.category,
        "num_trades": row.num_trades or 0,
        "total_volume": _to_decimal(row.total_volume),
        "total_pnl": _to_decimal(row.total_pnl),
        "roi": _to_decimal(row.roi),
        "win_rate": _to_decimal(row.win_rate),
        "profit_factor": _to_decimal(row.profit_factor),
        "avg_position_size": _to_decimal(row.avg_position_size),
        "is_specialist": row.is_specialist if hasattr(row, "is_specialist") else False,
        "category_rank": row.category_rank if hasattr(row, "category_rank") else None,
    }


def analytic_to_category_detail(
    row: CategoryAnalytic,
) -> dict[str, Any]:
    avg_duration = row.avg_holding_duration
    avg_duration_str = str(avg_duration) if avg_duration is not None else None

    return {
        "wallet": row.wallet,
        "category": row.category,
        "num_trades": row.num_trades or 0,
        "total_volume": _to_decimal(row.total_volume),
        "total_cost_basis": _to_decimal(row.total_cost_basis),
        "total_pnl": _to_decimal(row.total_pnl),
        "total_realized_pnl": _to_decimal(row.total_realized_pnl),
        "total_unrealized_pnl": _to_decimal(row.total_unrealized_pnl),
        "roi": _to_decimal(row.roi),
        "win_rate": _to_decimal(row.win_rate),
        "num_resolved_positions": row.num_resolved_positions or 0,
        "profit_factor": _to_decimal(row.profit_factor),
        "avg_position_size": _to_decimal(row.avg_position_size),
        "avg_holding_duration": avg_duration_str,
        "is_specialist": row.is_specialist if hasattr(row, "is_specialist") else False,
        "category_rank": row.category_rank if hasattr(row, "category_rank") else None,
    }
