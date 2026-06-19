from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CategoryAnalytic, CategoryRanking


async def get_categories(
    db: AsyncSession,
) -> list[str]:
    stmt = (
        select(CategoryAnalytic.category)
        .distinct()
        .order_by(CategoryAnalytic.category)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_wallet_categories(
    db: AsyncSession,
    address: str,
) -> list[CategoryAnalytic]:
    stmt = (
        select(CategoryAnalytic)
        .where(CategoryAnalytic.wallet == address)
        .order_by(CategoryAnalytic.category_rank.asc().nulls_last())
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


async def get_category_detail(
    db: AsyncSession,
) -> tuple[list[str], int, Optional[date]]:
    stmt = select(CategoryAnalytic.category).distinct().order_by(CategoryAnalytic.category)
    result = await db.execute(stmt)
    categories = list(result.scalars().all())

    count_stmt = select(CategoryAnalytic.wallet).distinct()
    count_result = await db.execute(count_stmt)
    total_wallets = len(count_result.scalars().all())

    date_stmt = (
        select(CategoryAnalytic.snapshot_date)
        .order_by(CategoryAnalytic.snapshot_date.desc())
        .limit(1)
    )
    date_result = await db.execute(date_stmt)
    snapshot_date = date_result.scalar_one_or_none()

    return categories, total_wallets, snapshot_date
