# Phase 5 — Follow & Paper Trading — Portfolio API

> **Goal**: Expose paper trading portfolio status, positions, and trade history via REST API.
> **AI Agent Instructions**: Create `app/api/v1/portfolio.py` with all portfolio-related endpoints, register in `app/api/router.py`.

---

## Endpoints

### `GET /api/v1/portfolio`

Portfolio overview — balance, PnL, ROI, position count.

**Response `200 OK`:**
```json
{
  "id": "uuid",
  "name": "Main",
  "initial_balance": 10000.00,
  "current_balance": 9420.50,
  "total_realized_pnl": -350.00,
  "total_unrealized_pnl": -229.50,
  "total_pnl": -579.50,
  "total_roi": -5.795,
  "total_trades": 12,
  "total_volume": 8500.00,
  "created_at": "2026-06-29T12:00:00+00:00",
  "updated_at": "2026-06-29T14:00:00+00:00"
}
```

**When no portfolio exists:**
```json
{
  "id": null,
  "name": "Main",
  "initial_balance": 10000.00,
  "current_balance": 10000.00,
  "total_realized_pnl": 0,
  "total_unrealized_pnl": 0,
  "total_pnl": 0,
  "total_roi": 0,
  "total_trades": 0,
  "total_volume": 0,
  "created_at": null,
  "updated_at": null,
  "message": "No portfolio yet — follow a wallet with auto-copy enabled to create one."
}
```

---

### `GET /api/v1/portfolio/positions`

List all positions, filterable by status.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | str | `OPEN` | `OPEN`, `CLOSED`, `RESOLVED`, or `ALL` |
| `limit` | int | 50 | 1–200 |
| `offset` | int | 0 | ≥ 0 |

**Response `200 OK`:**
```json
{
  "data": [
    {
      "id": "uuid",
      "market_id": "0xmarket...",
      "outcome": "Yes",
      "side": "BUY",
      "status": "OPEN",
      "shares": 120.5,
      "avg_entry_price": 0.42,
      "current_price": 0.38,
      "cost_basis": 50.61,
      "realized_pnl": 0,
      "unrealized_pnl": -4.82,
      "followed_wallet": "0x1234...abcd",
      "opened_at": "2026-06-29T12:00:00+00:00",
      "closed_at": null
    }
  ],
  "total": 1
}
```

---

### `GET /api/v1/portfolio/trades`

Paginated trade history.

**Query Parameters:**

| Param | Type | Default | Valid Range | Description |
|-------|------|---------|-------------|-------------|
| `limit` | int | 50 | 1–200 | Max results |
| `offset` | int | 0 | ≥ 0 | Pagination offset |

**Response `200 OK`:**
```json
{
  "data": [
    {
      "id": "uuid",
      "market_id": "0xmarket...",
      "outcome": "Yes",
      "side": "BUY",
      "price": 0.42,
      "shares": 120.5,
      "amount_usd": 50.61,
      "followed_wallet": "0x1234...abcd",
      "copy_mode": "proportional",
      "copy_value_used": 0.05,
      "executed_at": "2026-06-29T12:05:00+00:00"
    }
  ],
  "limit": 50,
  "offset": 0,
  "total": 12
}
```

---

### `POST /api/v1/portfolio/positions/{id}/close`

Manually close an open position at current market price.

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `id` | UUID | Position ID |

**Request Body:** (empty)

**Response `200 OK`:**
```json
{
  "executed": true,
  "position_id": "uuid",
  "side": "SELL",
  "shares": 120.5,
  "price": 0.38,
  "amount_usd": 45.79,
  "realized_pnl": -4.82,
  "new_balance": 9466.29
}
```

**Error Responses:**

| Status | Body | When |
|--------|------|------|
| 404 | `{"detail": "Position not found"}` | Unknown position ID |
| 409 | `{"detail": "Position is already closed"}` | Position not OPEN |

---

### `POST /api/v1/portfolio/reset`

Reset portfolio to a new initial balance (clears all positions and trades).

**Request Body:**
```json
{
  "initial_balance": 10000.00
}
```

**Response `200 OK`:**
```json
{
  "portfolio": {
    "id": "uuid",
    "initial_balance": 10000.00,
    "current_balance": 10000.00,
    "total_pnl": 0,
    "total_roi": 0,
    "total_trades": 0,
    ...
  },
  "message": "Portfolio reset successfully. All positions and trades cleared."
}
```

---

## Router Implementation

```python
# app/api/v1/portfolio.py

from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.db.models import PaperPortfolio, PaperPosition, PaperTrade
from app.models.schemas import (
    PortfolioResponse, PortfolioResetRequest, PortfolioResetResponse,
    PaperPositionResponse, PaperPositionListResponse,
    PaperTradeResponse, PaperTradeListResponse,
)

router = APIRouter()


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(db: AsyncSession = Depends(get_db)):
    """Get paper trading portfolio overview."""
    result = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.user_id == "default")
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
):
    """List paper positions."""
    portfolio = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.user_id == "default")
    )
    portfolio = portfolio.scalar_one_or_none()
    if portfolio is None:
        return PaperPositionListResponse(data=[], total=0)

    stmt = select(PaperPosition).where(
        PaperPosition.portfolio_id == portfolio.id,
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
):
    """List paper trade history."""
    portfolio = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.user_id == "default")
    )
    portfolio = portfolio.scalar_one_or_none()
    if portfolio is None:
        return PaperTradeListResponse(data=[], limit=limit, offset=offset, total=0)

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(PaperTrade).where(
            PaperTrade.portfolio_id == portfolio.id
        )
    )
    total = count_result.scalar() or 0

    stmt = (
        select(PaperTrade)
        .where(PaperTrade.portfolio_id == portfolio.id)
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
):
    """Manually close an open paper position at current market price."""
    result = await db.execute(
        select(PaperPosition).where(
            PaperPosition.id == position_id,
        )
    )
    position = result.scalar_one_or_none()
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    if position.status != "OPEN":
        raise HTTPException(status_code=409, detail="Position is already closed")

    # Get current price
    from app.services.paper_trading import _get_current_price
    current_price = await _get_current_price(db, position.market_id, position.outcome)
    if current_price is None:
        raise HTTPException(status_code=503, detail="Market price unavailable")

    # Close position
    sell_amount = position.shares * current_price
    realized_pnl = sell_amount - position.cost_basis

    position.status = "CLOSED"
    position.closed_at = func.now()
    position.current_price = current_price
    position.realized_pnl += realized_pnl
    position.unrealized_pnl = Decimal("0")

    # Update portfolio
    portfolio_result = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.id == position.portfolio_id)
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
):
    """Reset portfolio — clear all positions/trades, set new balance."""
    portfolio_result = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.user_id == "default")
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if portfolio is None:
        portfolio = PaperPortfolio(
            user_id="default",
            initial_balance=body.initial_balance,
            current_balance=body.initial_balance,
        )
        db.add(portfolio)
    else:
        # Delete all trades and positions for this portfolio
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
```

---

## Router Registration

Edit `app/api/router.py`:

```python
from app.api.v1.portfolio import router as portfolio_router

api_router.include_router(portfolio_router, prefix="/portfolio", tags=["portfolio"])
```

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `app/api/v1/portfolio.py` |
| EDIT | `app/api/router.py` — register portfolio router |

---

## Verification

```bash
# Portfolio overview
curl "http://localhost:8000/api/v1/portfolio"

# List positions
curl "http://localhost:8000/api/v1/portfolio/positions"

# Trade history
curl "http://localhost:8000/api/v1/portfolio/trades?limit=10"

# Close a position (replace UUID)
curl -X POST "http://localhost:8000/api/v1/portfolio/positions/uuid-here/close"

# Reset portfolio
curl -X POST "http://localhost:8000/api/v1/portfolio/reset" \
  -H "Content-Type: application/json" \
  -d '{"initial_balance": 50000}'
```
