from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.enums import MarketCategory
from app.models.schemas import (
    CategoryDetailResponse,
    CategoryItem,
    CategoryLeaderboardEntry,
    CategoryLeaderboardResponse,
    WalletCategoryResponse,
    WalletCategorySummary,
)
from app.services.category_service import (
    analytic_to_category_detail,
    analytic_to_category_summary,
    get_category_labels,
    get_category_leaderboard as get_category_leaderboard_data,
    get_wallet_categories as get_wallet_categories_data,
    get_wallet_category_detail as get_wallet_category_detail_data,
    wallet_exists,
)
from app.utils.category import validate_category
from app.utils.decimal_helpers import to_decimal

router = APIRouter()


def _validate_category_or_404(category: str) -> str:
    """Validate a category string, raising 404 if invalid."""
    norm = validate_category(category)
    if norm is None:
        valid = sorted(m.value for m in MarketCategory)
        raise HTTPException(
            status_code=404,
            detail=f"Invalid category '{category}'. Valid categories: {', '.join(valid)}",
        )
    return norm


def _build_leaderboard_entry(
    row: Any,
    is_specialist: bool = False,
) -> CategoryLeaderboardEntry:
    return CategoryLeaderboardEntry(
        rank=row.rank,
        wallet=row.wallet,
        wallet_score=to_decimal(getattr(row, "wallet_score", None)),
        roi=to_decimal(getattr(row, "roi", None)),
        win_rate=to_decimal(getattr(row, "win_rate", None)),
        total_pnl=to_decimal(getattr(row, "total_pnl", None)),
        num_trades=row.num_trades or 0,
        total_volume=to_decimal(getattr(row, "total_volume", None)),
        is_specialist=is_specialist,
    )


@router.get(
    "/categories",
    response_model=list[CategoryItem],
    summary="List Categories",
    description="Return all known categories with their labels.",
)
async def list_categories(
    db: AsyncSession = Depends(get_db),
) -> list[CategoryItem]:
    rows = await get_category_labels(db)
    return [CategoryItem(category=str(r.category), label=str(r.label)) for r in rows]


@router.get(
    "/leaderboard/{category}",
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
    norm_category = _validate_category_or_404(category)
    entries = await get_category_leaderboard_data(db, norm_category, limit=limit, offset=offset)

    return CategoryLeaderboardResponse(
        category=category.lower(),
        data=[_build_leaderboard_entry(e) for e in entries],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/leaderboard/{category}/specialists",
    response_model=CategoryLeaderboardResponse,
    summary="Category Specialists",
    description="Specialist traders in a specific category.",
)
async def category_specialists(
    category: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> CategoryLeaderboardResponse:
    norm_category = _validate_category_or_404(category)
    entries = await get_category_leaderboard_data(db, norm_category, list_type="specialists", limit=limit)

    return CategoryLeaderboardResponse(
        category=category.lower(),
        data=[_build_leaderboard_entry(e, is_specialist=True) for e in entries],
        limit=limit,
        offset=0,
    )


@router.get(
    "/wallets/{address}/categories",
    response_model=WalletCategoryResponse,
    summary="Wallet Categories",
    description="Per-category performance breakdown for a specific wallet.",
)
async def wallet_categories(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletCategoryResponse:
    if not await wallet_exists(db, address):
        raise HTTPException(status_code=404, detail="Wallet not found")

    rows = await get_wallet_categories_data(db, address)

    return WalletCategoryResponse(
        wallet=address,
        categories=[WalletCategorySummary(**analytic_to_category_summary(r)) for r in rows],
    )


@router.get(
    "/wallets/{address}/categories/{category}",
    response_model=CategoryDetailResponse,
    summary="Wallet Category Detail",
    description="Detailed analytics for a specific wallet+category combination.",
)
async def wallet_category_detail(
    address: str,
    category: str,
    db: AsyncSession = Depends(get_db),
) -> CategoryDetailResponse:
    norm_category = _validate_category_or_404(category)
    if not await wallet_exists(db, address):
        raise HTTPException(status_code=404, detail="Wallet not found")

    row = await get_wallet_category_detail_data(db, address, norm_category)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for wallet '{address}' in category '{category}'",
        )

    return CategoryDetailResponse(**analytic_to_category_detail(row))
