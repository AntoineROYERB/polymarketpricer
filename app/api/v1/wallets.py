from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.db.models import Wallet
from app.models.schemas import (
    WalletAnalyticsData, WalletCategorySummary, WalletProfile,
    WalletEdgeSnapshot as WalletEdgeSnapshotSchema,
)
from app.services.category_service import (
    analytic_to_category_summary,
)
from app.services.category_service import (
    get_wallet_categories as get_wallet_categories_data,
)
from app.services.wallet_service import (
    get_latest_edge_snapshot,
    get_wallet_analytics,
    get_wallet_positions,
    get_wallet_profile,
)
router = APIRouter()


@router.get(
    "/{address}",
    response_model=WalletProfile,
    summary="Wallet Profile",
    description="Detailed profile with analytics, positions, categories, and edge metrics.",
)
async def wallet_profile(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletProfile:
    wallet = await get_wallet_profile(db, address)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    analytics = await get_wallet_analytics(db, address)
    positions = await get_wallet_positions(db, address)
    categories = await get_wallet_categories_data(db, address)

    profile = WalletProfile.model_validate(wallet)

    if analytics is not None:
        analytics_data = WalletAnalyticsData.model_validate(analytics)
        if analytics.avg_holding_duration is not None:
            analytics_data.avg_holding_duration = str(analytics.avg_holding_duration)
        profile.analytics = analytics_data

    profile.current_positions = positions
    profile.categories = [
        WalletCategorySummary(**analytic_to_category_summary(r)) for r in categories
    ]

    edge_snapshot = await get_latest_edge_snapshot(db, address)
    if edge_snapshot is not None:
        profile.edge_metrics = WalletEdgeSnapshotSchema.model_validate(edge_snapshot)

    return profile


@router.get(
    "/{address}/edge",
    response_model=WalletEdgeSnapshotSchema,
    summary="Wallet Edge Metrics",
    description="Latest edge snapshot for a specific wallet.",
)
async def wallet_edge(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletEdgeSnapshotSchema:
    w = await db.execute(select(Wallet).where(Wallet.wallet == address))
    if w.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    snapshot = await get_latest_edge_snapshot(db, address)

    if snapshot is None:
        return WalletEdgeSnapshotSchema(
            wallet=address,
            avg_edge=Decimal("0"),
            num_edge_trades=0,
        )

    return WalletEdgeSnapshotSchema.model_validate(snapshot)
