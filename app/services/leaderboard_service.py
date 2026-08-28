from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RankingSnapshot

LIST_TYPE_ALLOWED = {"top_100", "emerging", "consistent"}


async def get_ranking_list(
    db: AsyncSession,
    list_type: str = "top_100",
    limit: int = 100,
    offset: int = 0,
) -> list[RankingSnapshot]:
    if list_type not in LIST_TYPE_ALLOWED:
        raise ValueError(f"Invalid list_type '{list_type}'. Must be one of: {', '.join(sorted(LIST_TYPE_ALLOWED))}")

    # ranking_snapshots keeps one row per (wallet, snapshot_date, list_type);
    # a leaderboard is a single day's ranking, so pin it to the latest snapshot
    # for this list — otherwise every historical run is concatenated and ranks
    # repeat.
    latest_date = (
        select(func.max(RankingSnapshot.snapshot_date))
        .where(RankingSnapshot.list_type == list_type)
        .scalar_subquery()
    )

    stmt = (
        select(RankingSnapshot)
        .where(
            RankingSnapshot.list_type == list_type,
            RankingSnapshot.snapshot_date == latest_date,
        )
        .order_by(RankingSnapshot.rank)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
