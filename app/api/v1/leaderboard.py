from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.db.models import WalletEdgeSnapshot
from app.models.schemas import (
    CategoryLeaderboardEntry,
    CategoryLeaderboardResponse,
    EdgeLeaderboardEntry,
    EdgeLeaderboardResponse,
    LeaderboardEntry,
    LeaderboardResponse,
)
from app.services.category_service import (
    get_category_leaderboard as get_category_leaderboard_data,
)
from app.services.leaderboard_service import get_ranking_list
from app.utils.category import validate_category_or_404
from app.utils.decimal_helpers import to_decimal

router = APIRouter()


@router.get(
    "",
    response_model=LeaderboardResponse,
    summary="Leaderboard",
    description="Top 100 traders ranked by composite wallet score. Score = 0.40×edge_score + 0.20×consistency_score + 0.20×normalized_roi + 0.10×experience_score + 0.10×normalized_sharpe.",
)
async def leaderboard(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardResponse:
    entries = await get_ranking_list(db, list_type="top_100", limit=limit, offset=offset)
    return LeaderboardResponse(
        data=[_to_entry(e) for e in entries],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/emerging",
    response_model=list[LeaderboardEntry],
    summary="Emerging Traders",
    description="Top 10 mid-experience traders (experience_score between 0.3 and 0.6) ranked by wallet score. Catches rising traders before they reach the top 100.",
)
async def emerging(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[LeaderboardEntry]:
    entries = await get_ranking_list(db, list_type="emerging", limit=limit)
    return [_to_entry(e) for e in entries]


@router.get(
    "/consistent",
    response_model=list[LeaderboardEntry],
    summary="Consistent Traders",
    description="Top 10 traders by consistency score (1 / (1 + CV of trade PnLs), requiring ≥10 trades). Rewards traders with steady, low-variance returns.",
)
async def consistent(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[LeaderboardEntry]:
    entries = await get_ranking_list(db, list_type="consistent", limit=limit)
    return [_to_entry(e) for e in entries]


def _safe_decimal(row: Any, attr: str) -> Decimal | None:
    return to_decimal(getattr(row, attr, None))


def _to_entry(e: Any) -> LeaderboardEntry:
    return LeaderboardEntry(
        rank=getattr(e, "rank", 0),
        wallet=e.wallet,
        score=_safe_decimal(e, "wallet_score"),
        roi=_safe_decimal(e, "roi"),
        win_rate=_safe_decimal(e, "win_rate"),
        total_pnl=_safe_decimal(e, "total_pnl"),
        num_trades=e.num_trades or 0,
        consistency_score=_safe_decimal(e, "consistency_score"),
        experience_score=_safe_decimal(e, "experience_score"),
        edge_score=_safe_decimal(e, "edge_score"),
        edge_consistency=_safe_decimal(e, "edge_consistency"),
        num_edge_trades=getattr(e, "num_edge_trades", 0) or 0,
    )


@router.get(
    "/edge",
    response_model=EdgeLeaderboardResponse,
    summary="Edge Leaderboard",
    description="Traders ranked by edge score. Edge per trade = (exit_price - entry_price) / entry_price. Wallet edge_score = min-max normalized avg_edge across all wallets ([0,1]). Also shows edge_consistency = proportion of trades with positive edge.",
)
async def edge_leaderboard(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> EdgeLeaderboardResponse:
    stmt = (
        select(WalletEdgeSnapshot)
        .where(WalletEdgeSnapshot.edge_score.isnot(None))
        .order_by(WalletEdgeSnapshot.edge_score.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    data = [
        EdgeLeaderboardEntry(
            wallet=r.wallet,
            edge_score=to_decimal(r.edge_score),
            avg_edge=to_decimal(r.avg_edge),
            edge_consistency=to_decimal(r.edge_consistency) if r.edge_consistency else None,
            num_edge_trades=r.num_edge_trades,
            rank=offset + idx + 1,
        )
        for idx, r in enumerate(rows)
    ]

    return EdgeLeaderboardResponse(data=data, limit=limit, offset=offset)


def _build_leaderboard_entry(
    row: Any,
    is_specialist: bool = False,
) -> CategoryLeaderboardEntry:
    return CategoryLeaderboardEntry(
        rank=row.rank,
        wallet=row.wallet,
        wallet_score=_safe_decimal(row, "wallet_score"),
        roi=_safe_decimal(row, "roi"),
        win_rate=_safe_decimal(row, "win_rate"),
        total_pnl=_safe_decimal(row, "total_pnl"),
        num_trades=row.num_trades or 0,
        total_volume=_safe_decimal(row, "total_volume"),
        is_specialist=is_specialist,
    )


@router.get(
    "/{category}",
    response_model=CategoryLeaderboardResponse,
    summary="Category Leaderboard",
    description="Top traders in a specific category, ranked by wallet_score.",
)
async def category_leaderboard(
    category: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CategoryLeaderboardResponse:
    norm_category = validate_category_or_404(category)
    entries = await get_category_leaderboard_data(db, norm_category, limit=limit, offset=offset)

    return CategoryLeaderboardResponse(
        category=category.lower(),
        data=[_build_leaderboard_entry(e) for e in entries],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{category}/specialists",
    response_model=CategoryLeaderboardResponse,
    summary="Category Specialists",
    description="Specialist traders in a specific category.",
)
async def category_specialists(
    category: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> CategoryLeaderboardResponse:
    norm_category = validate_category_or_404(category)
    entries = await get_category_leaderboard_data(db, norm_category, list_type="specialists", limit=limit)

    return CategoryLeaderboardResponse(
        category=category.lower(),
        data=[_build_leaderboard_entry(e, is_specialist=True) for e in entries],
        limit=limit,
        offset=0,
    )
