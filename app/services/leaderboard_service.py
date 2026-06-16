from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RankingSnapshot


async def get_leaderboard(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> list[RankingSnapshot]:
    stmt = (
        select(RankingSnapshot)
        .where(RankingSnapshot.list_type == "top_100")
        .order_by(RankingSnapshot.rank)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_top_emerging(
    db: AsyncSession,
    limit: int = 10,
) -> list[RankingSnapshot]:
    stmt = (
        select(RankingSnapshot)
        .where(RankingSnapshot.list_type == "emerging")
        .order_by(RankingSnapshot.rank)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_top_consistent(
    db: AsyncSession,
    limit: int = 10,
) -> list[RankingSnapshot]:
    stmt = (
        select(RankingSnapshot)
        .where(RankingSnapshot.list_type == "consistent")
        .order_by(RankingSnapshot.rank)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
