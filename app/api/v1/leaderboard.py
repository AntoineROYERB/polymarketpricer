from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.schemas import LeaderboardEntry, LeaderboardResponse
from app.services.leaderboard_service import (
    get_leaderboard as get_leaderboard_data,
    get_top_consistent,
    get_top_emerging,
)

router = APIRouter()


@router.get("", response_model=LeaderboardResponse)
async def leaderboard(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardResponse:
    entries = await get_leaderboard_data(db, limit=limit, offset=offset)
    return LeaderboardResponse(
        data=[_to_entry(e) for e in entries],
        limit=limit,
        offset=offset,
    )


@router.get("/emerging", response_model=list[LeaderboardEntry])
async def emerging(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[LeaderboardEntry]:
    entries = await get_top_emerging(db, limit=limit)
    return [_to_entry(e) for e in entries]


@router.get("/consistent", response_model=list[LeaderboardEntry])
async def consistent(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[LeaderboardEntry]:
    entries = await get_top_consistent(db, limit=limit)
    return [_to_entry(e) for e in entries]


def _to_entry(e: Any) -> LeaderboardEntry:
    def _d(val: Any) -> Decimal:
        if val is None:
            return Decimal(0)
        return Decimal(str(val))

    return LeaderboardEntry(
        rank=getattr(e, "rank", 0),
        wallet=e.wallet,
        score=_d(getattr(e, "wallet_score", None)),
        roi=_d(getattr(e, "roi", None)),
        win_rate=_d(getattr(e, "win_rate", None)),
        total_pnl=_d(getattr(e, "total_pnl", None)),
        num_trades=e.num_trades or 0,
        consistency_score=_d(getattr(e, "consistency_score", None)),
        experience_score=_d(getattr(e, "experience_score", None)),
    )
