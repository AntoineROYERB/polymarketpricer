from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WalletAnalytic


async def get_leaderboard(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> list[WalletAnalytic]:
    stmt = (
        select(WalletAnalytic)
        .where(WalletAnalytic.wallet_score.isnot(None))
        .order_by(desc(WalletAnalytic.wallet_score))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_top_emerging(
    db: AsyncSession,
    limit: int = 10,
) -> list[WalletAnalytic]:
    stmt = (
        select(WalletAnalytic)
        .where(WalletAnalytic.wallet_score.isnot(None))
        .order_by(desc(WalletAnalytic.wallet_score))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_top_consistent(
    db: AsyncSession,
    limit: int = 10,
) -> list[WalletAnalytic]:
    stmt = (
        select(WalletAnalytic)
        .where(WalletAnalytic.wallet_score.isnot(None))
        .order_by(desc(WalletAnalytic.wallet_score))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
