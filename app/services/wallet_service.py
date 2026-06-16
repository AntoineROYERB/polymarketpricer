from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, Position, Wallet, WalletAnalytic
from app.models.schemas import PositionSummary


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
) -> list[PositionSummary]:
    stmt = (
        select(Position, Market.question)
        .join(Market, Position.market_id == Market.id)
        .where(Position.wallet == address)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        PositionSummary(
            market_id=p.market_id,
            question=q,
            side=p.side.value if p.side else None,
            status=p.status.value if p.status else "OPEN",
            shares=p.shares,
            avg_entry_price=p.avg_entry_price,
            entry_time=p.entry_time,
            exit_time=p.exit_time,
            realized_pnl=p.realized_pnl,
            unrealized_pnl=p.unrealized_pnl,
            total_pnl=p.total_pnl,
        )
        for p, q in rows
    ]
