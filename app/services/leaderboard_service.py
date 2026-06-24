from sqlalchemy import select
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

    stmt = (
        select(RankingSnapshot)
        .where(RankingSnapshot.list_type == list_type)
        .order_by(RankingSnapshot.rank)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
