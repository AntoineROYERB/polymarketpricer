from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.db.models import Market
from app.models.schemas import MarketListResponse, MarketSummary

router = APIRouter()


@router.get("", response_model=MarketListResponse)
async def markets(
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> MarketListResponse:
    from app.utils.category import validate_category

    stmt = select(Market)
    if category is not None:
        norm_category = validate_category(category)
        if norm_category is None:
            return MarketListResponse(data=[], limit=limit, offset=offset)
        stmt = stmt.where(Market.category == norm_category)
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return MarketListResponse(
        data=[MarketSummary.model_validate(r) for r in rows],
        limit=limit,
        offset=offset,
    )
