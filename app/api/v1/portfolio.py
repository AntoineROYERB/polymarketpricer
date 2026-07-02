# mypy: disable-error-code="assignment"

from uuid import UUID
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.api.dependencies.auth import optional_api_key
from app.db.models import PaperPortfolio, PaperPosition, PaperTrade
from app.models.schemas import (
    PortfolioResponse, PortfolioResetRequest, PortfolioResetResponse,
    PaperPositionResponse, PaperPositionListResponse,
    PaperTradeResponse, PaperTradeListResponse,
)
from app.services.paper_trading import _get_current_price

router = APIRouter()


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(optional_api_key),
) -> PortfolioResponse:
    """Get paper trading portfolio overview."""
    result = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        return PortfolioResponse(
            id=None, name="Main", initial_balance=Decimal("10000"),
            current_balance=Decimal("10000"), total_realized_pnl=Decimal("0"),
            total_unrealized_pnl=Decimal("0"), total_pnl=Decimal("0"),
            total_roi=Decimal("0"), total_trades=0, total_volume=Decimal("0"),
        )
    return PortfolioResponse.model_validate(portfolio)


@router.get("/positions", response_model=PaperPositionListResponse)
async def list_positions(
    status_filter: str = Query(default="OPEN", alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(optional_api_key),
) -> PaperPositionListResponse:
    """List paper positions."""
    portfolio = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
    )
    pf = portfolio.scalar_one_or_none()
    if pf is None:
        return PaperPositionListResponse(data=[], total=0)

    stmt = select(PaperPosition).where(
        PaperPosition.portfolio_id == pf.id,
    )
    if status_filter.upper() != "ALL":
        stmt = stmt.where(PaperPosition.status == status_filter.upper())
    stmt = stmt.order_by(PaperPosition.opened_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return PaperPositionListResponse(
        data=[PaperPositionResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.get("/trades", response_model=PaperTradeListResponse)
async def list_trades(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(optional_api_key),
) -> PaperTradeListResponse:
    """List paper trade history."""
    portfolio = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
    )
    pf = portfolio.scalar_one_or_none()
    if pf is None:
        return PaperTradeListResponse(data=[], limit=limit, offset=offset, total=0)

    count_result = await db.execute(
        select(func.count()).select_from(PaperTrade).where(
            PaperTrade.portfolio_id == pf.id
        )
    )
    total = count_result.scalar() or 0

    stmt = (
        select(PaperTrade)
        .where(PaperTrade.portfolio_id == pf.id)
        .order_by(PaperTrade.executed_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return PaperTradeListResponse(
        data=[PaperTradeResponse.model_validate(r) for r in rows],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.post("/positions/{position_id}/close")
async def close_position(
    position_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(optional_api_key),
) -> dict[str, Any]:
    """Manually close an open paper position at current market price."""
    result = await db.execute(
        select(PaperPosition).where(
            PaperPosition.id == position_id,
        ).with_for_update()
    )
    position = result.scalar_one_or_none()
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if position.status != "OPEN":
        raise HTTPException(status_code=409, detail="Position is already closed")

    # Ownership check: verify the position's portfolio belongs to this user
    portfolio_owner = await db.execute(
        select(PaperPortfolio).where(
            PaperPortfolio.id == position.portfolio_id,
            PaperPortfolio.user_id == user_id,
        )
    )
    if portfolio_owner.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Position not found")

    current_price = await _get_current_price(db, position.market_id, position.outcome)  # type: ignore[arg-type]
    if current_price is None:
        raise HTTPException(status_code=503, detail="Market price unavailable")

    sell_amount = position.shares * current_price
    realized_pnl = sell_amount - position.cost_basis

    position.status = "CLOSED"
    position.closed_at = func.now()
    position.current_price = current_price
    position.realized_pnl += realized_pnl
    position.unrealized_pnl = Decimal("0")

    portfolio_result = await db.execute(
        select(PaperPortfolio).where(
            PaperPortfolio.id == position.portfolio_id,
            PaperPortfolio.user_id == user_id,
        )
    )
    portfolio = portfolio_result.scalar_one()
    portfolio.current_balance += sell_amount
    portfolio.total_realized_pnl += realized_pnl
    portfolio.total_trades += 1
    portfolio.total_pnl = portfolio.total_realized_pnl + portfolio.total_unrealized_pnl

    await db.commit()

    return {
        "executed": True,
        "position_id": str(position_id),
        "side": "SELL",
        "shares": position.shares,
        "price": current_price,
        "amount_usd": sell_amount,
        "realized_pnl": realized_pnl,
        "new_balance": portfolio.current_balance,
    }


@router.post("/reset", response_model=PortfolioResetResponse)
async def reset_portfolio(
    body: PortfolioResetRequest = PortfolioResetRequest(),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(optional_api_key),
) -> PortfolioResetResponse:
    """Reset portfolio — clear all positions/trades, set new balance."""
    portfolio_result = await db.execute(
        select(PaperPortfolio).where(
            PaperPortfolio.user_id == user_id,
        ).with_for_update()
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if portfolio is None:
        portfolio = PaperPortfolio(
            user_id=user_id,
            name="Main",
            initial_balance=body.initial_balance,
            current_balance=body.initial_balance,
            total_realized_pnl=Decimal("0"),
            total_unrealized_pnl=Decimal("0"),
            total_pnl=Decimal("0"),
            total_trades=0,
            total_volume=Decimal("0"),
        )
        db.add(portfolio)
    else:
        await db.execute(
            delete(PaperTrade).where(PaperTrade.portfolio_id == portfolio.id)
        )
        await db.execute(
            delete(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
        )
        portfolio.initial_balance = body.initial_balance
        portfolio.current_balance = body.initial_balance
        portfolio.total_realized_pnl = Decimal("0")
        portfolio.total_unrealized_pnl = Decimal("0")
        portfolio.total_pnl = Decimal("0")
        portfolio.total_roi = None
        portfolio.total_trades = 0
        portfolio.total_volume = Decimal("0")

    await db.commit()
    await db.refresh(portfolio)

    return PortfolioResetResponse(
        portfolio=PortfolioResponse.model_validate(portfolio),
        message="Portfolio reset successfully. All positions and trades cleared.",
    )
