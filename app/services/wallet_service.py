from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Position, Wallet, WalletAnalytic


async def get_wallet_profile(
    db: AsyncSession,
    address: str,
) -> Optional[Wallet]:
    stmt = select(Wallet).where(Wallet.wallet == address)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_wallet_analytics(
    db: AsyncSession,
    address: str,
) -> Optional[WalletAnalytic]:
    stmt = (
        select(WalletAnalytic)
        .where(WalletAnalytic.wallet == address)
        .order_by(WalletAnalytic.snapshot_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_wallet_positions(
    db: AsyncSession,
    address: str,
) -> list[Position]:
    stmt = select(Position).where(Position.wallet == address)
    result = await db.execute(stmt)
    return list(result.scalars().all())
