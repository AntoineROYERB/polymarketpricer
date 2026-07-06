from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db
from app.db.models import Alert, Market, Outcome, Position
from app.models.schemas import (
    ActiveTraderEntry,
    MarketDetailResponse,
    MarketListResponse,
    MarketSummary,
    OutcomeResponse,
)

router = APIRouter()


@router.get(
    "",
    response_model=MarketListResponse,
    summary="List Markets",
    description="All markets, optionally filtered by category.",
)
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


@router.get(
    "/{market_id}",
    response_model=MarketDetailResponse,
    summary="Market Detail",
    description="Detailed market info including outcomes, sentiment, and active traders.",
)
async def market_detail(
    market_id: str,
    db: AsyncSession = Depends(get_db),
) -> MarketDetailResponse:
    result = await db.execute(
        select(Market)
        .where(Market.id == market_id)
        .options(selectinload(Market.outcomes))
    )
    market = result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    outcomes_result = await db.execute(
        select(Outcome).where(Outcome.market_id == market_id)
    )
    outcomes = outcomes_result.scalars().all()

    buy_count = await db.execute(
        select(sa_func.count(Alert.id)).where(
            Alert.market_id == market_id,
            Alert.action.in_(["NEW_POSITION", "INCREASE_POSITION"]),
        )
    )
    buy_total = buy_count.scalar() or 0

    sell_count = await db.execute(
        select(sa_func.count(Alert.id)).where(
            Alert.market_id == market_id,
            Alert.action.in_(["CLOSE_POSITION", "DECREASE_POSITION"]),
        )
    )
    sell_total = sell_count.scalar() or 0
    total_alerts = buy_total + sell_total
    buy_percent = round((buy_total / total_alerts) * 100, 1) if total_alerts > 0 else 50.0

    from app.utils.decimal_helpers import to_decimal

    trader_rows = await db.execute(
        select(
            Alert.wallet,
            Alert.action,
            Alert.position_size,
            Alert.price,
        )
        .where(Alert.market_id == market_id)
        .distinct(Alert.wallet)
        .order_by(Alert.wallet, Alert.detected_at.desc())
        .limit(20)
    )
    active_traders = []
    for row in trader_rows.all():
        pnl_result = await db.execute(
            select(Position.total_pnl).where(
                Position.wallet == row.wallet,
                Position.market_id == market_id,
            )
        )
        pnl = pnl_result.scalar_one_or_none()

        side = "BUY" if row.action in ("NEW_POSITION", "INCREASE_POSITION") else "SELL"
        active_traders.append(
            ActiveTraderEntry(
                wallet=row.wallet,
                side=side,
                position_size=float(to_decimal(row.position_size)),
                price=float(to_decimal(row.price)),
                total_pnl=float(to_decimal(pnl)) if pnl is not None else None,
            )
        )

    response = MarketDetailResponse.model_validate(market)
    response.category = market.category if market.category else market.mapped_category  # type: ignore[assignment]
    response.outcomes = [OutcomeResponse.model_validate(o) for o in outcomes]
    response.buy_percent = buy_percent
    response.active_traders = active_traders
    return response
