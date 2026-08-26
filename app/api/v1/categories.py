from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.schemas import (
    CategoryDetailResponse,
    CategoryItem,
    WalletCategoryResponse,
    WalletCategorySummary,
)
from app.services.category_service import (
    analytic_to_category_detail,
    analytic_to_category_summary,
    get_category_labels,
    wallet_exists,
)
from app.services.category_service import (
    get_wallet_categories as get_wallet_categories_data,
)
from app.services.category_service import (
    get_wallet_category_detail as get_wallet_category_detail_data,
)
from app.utils.category import validate_category_or_404

router = APIRouter()


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
    norm_category = validate_category_or_404(category)
    if not await wallet_exists(db, address):
        raise HTTPException(status_code=404, detail="Wallet not found")

    row = await get_wallet_category_detail_data(db, address, norm_category)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for wallet '{address}' in category '{category}'",
        )

    return CategoryDetailResponse(**analytic_to_category_detail(row))
