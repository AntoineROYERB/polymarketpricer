from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.schemas import WalletAnalyticsData, WalletProfile
from app.services.wallet_service import (
    get_wallet_analytics,
    get_wallet_positions,
    get_wallet_profile,
)

router = APIRouter()


@router.get("/{address}", response_model=WalletProfile)
async def wallet_profile(
    address: str,
    db: AsyncSession = Depends(get_db),
):
    wallet = await get_wallet_profile(db, address)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    analytics = await get_wallet_analytics(db, address)
    positions = await get_wallet_positions(db, address)

    profile = WalletProfile.model_validate(wallet)

    if analytics is not None:
        analytics_data = WalletAnalyticsData.model_validate(analytics)
        if analytics.avg_holding_duration is not None:
            analytics_data.avg_holding_duration = str(analytics.avg_holding_duration)
        profile.analytics = analytics_data

    profile.current_positions = positions

    return profile
