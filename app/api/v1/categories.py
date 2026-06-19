from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.schemas import (
    CategoryAnalyticsData,
    CategoryDetailResponse,
    CategoryLeaderboardEntry,
    CategoryLeaderboardResponse,
    WalletCategoryResponse,
    WalletCategorySummary,
)
from app.services.category_service import (
    get_categories,
    get_wallet_categories,
    get_category_leaderboard,
    get_category_detail,
)

router = APIRouter()


@router.get("/", response_model=CategoryDetailResponse)
async def category_detail(
    db: AsyncSession = Depends(get_db),
) -> CategoryDetailResponse:
    categories, total_wallets, snapshot_date = await get_category_detail(db)
    return CategoryDetailResponse(
        categories=categories,
        total_wallets_tracked=total_wallets,
        snapshot_date=snapshot_date,
    )


@router.get("/{category}/leaderboard", response_model=CategoryLeaderboardResponse)
async def category_leaderboard(
    category: str,
    list_type: str = Query("top_50", pattern="^(top_50|specialists)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CategoryLeaderboardResponse:
    rows = await get_category_leaderboard(
        db, category, list_type=list_type, limit=limit, offset=offset
    )
    return CategoryLeaderboardResponse(
        category=category,
        list_type=list_type,
        data=[
            CategoryLeaderboardEntry(
                rank=r.rank,
                wallet=r.wallet,
                wallet_score=r.wallet_score,
                roi=r.roi,
                win_rate=r.win_rate,
                total_pnl=r.total_pnl,
                num_trades=r.num_trades,
                total_volume=r.total_volume,
            )
            for r in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/wallet/{address}", response_model=WalletCategoryResponse)
async def wallet_categories(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletCategoryResponse:
    rows = await get_wallet_categories(db, address)
    return WalletCategoryResponse(
        data=WalletCategorySummary(
            wallet=address,
            categories=[
                CategoryAnalyticsData(
                    category=r.category,
                    num_trades=r.num_trades,
                    total_volume=r.total_volume,
                    total_cost_basis=r.total_cost_basis,
                    total_pnl=r.total_pnl,
                    total_realized_pnl=r.total_realized_pnl,
                    total_unrealized_pnl=r.total_unrealized_pnl,
                    roi=r.roi,
                    win_rate=r.win_rate,
                    num_resolved_positions=r.num_resolved_positions,
                    profit_factor=r.profit_factor,
                    avg_position_size=r.avg_position_size,
                    avg_holding_duration=str(r.avg_holding_duration)
                    if r.avg_holding_duration
                    else None,
                    is_specialist=r.is_specialist,
                    category_rank=r.category_rank,
                )
                for r in rows
            ],
        )
    )
