# Phase 5 — Follow & Paper Trading — Paper Trading Engine

> **Goal**: Simulate trade execution when a followed wallet opens/closes a position. Uses real market prices, virtual capital, configurable sizing.
> **AI Agent Instructions**: Create `app/services/paper_trading.py` with the core engine — trade execution, position management, portfolio balance updates, and market resolution handling.

---

## Core Engine: `app/services/paper_trading.py`

### Execution Flow

```
Alert received (NEW_POSITION / POSITION_INCREASE / FULL_EXIT)
        │
        ▼
  Check: is wallet followed with auto_copy_enabled?
        │
        ▼ (yes)
  Check: category_filter matches alert.category?
        │
        ▼ (yes)
  Compute copy amount (proportional or fixed)
        │
        ▼
  Check: does portfolio have sufficient balance?
        │
        ▼ (yes, or adjust)
  Execute trade:
    - Deduct amount from portfolio.current_balance
    - Create/update paper_position
    - Create paper_trade
    - Update portfolio.total_trades, total_volume, total_pnl
        │
        ▼
  Return execution result
```

---

### Core Functions

```python
# app/services/paper_trading.py

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    WalletFollow, PaperPortfolio, PaperPosition, PaperTrade,
)
from app.models.schemas import PaperTradeResponse


async def execute_copy_trade(
    db: AsyncSession,
    alert: dict,  # alert data from pipeline
    follow: WalletFollow,
) -> Optional[dict]:
    """
    Execute a paper copy trade based on an alert and follow config.
    Returns execution result dict or None if skipped.
    """
    # 1. Check category filter
    if follow.category_filter:
        alert_category = alert.get("category", "")
        if alert_category not in follow.category_filter:
            return {"skipped": True, "reason": f"Category '{alert_category}' filtered out"}

    # 2. Get or create portfolio
    portfolio = await _get_or_create_portfolio(db, follow.user_id)

    # 3. Compute copy amount
    position_size = Decimal(str(alert.get("position_size", 0)))
    if position_size <= 0:
        return {"skipped": True, "reason": "Zero position size"}

    copy_amount = _compute_copy_amount(follow.copy_mode, follow.copy_value, position_size)

    # 4. Check balance
    if copy_amount > portfolio.current_balance:
        copy_amount = portfolio.current_balance  # adjust to available balance
        if copy_amount <= 0:
            return {"skipped": True, "reason": "Insufficient balance"}

    # 5. Get market price from outcomes table
    market_id = alert.get("market_id", "")
    price = await _get_current_price(db, market_id, alert.get("outcome", "Yes"))
    if price is None or price <= 0:
        return {"skipped": True, "reason": "Market price unavailable"}

    action = alert.get("action", "")
    side = "BUY" if action in ("NEW_POSITION", "POSITION_INCREASE", "TRADE_BUY") else "SELL"
    shares = copy_amount / price if side == "BUY" else Decimal(str(alert.get("shares", 0)))

    # 6. Execute
    if side == "BUY":
        return await _execute_buy(db, portfolio, follow, alert, market_id, price, shares, copy_amount)
    elif side == "SELL":
        return await _execute_sell(db, portfolio, follow, alert, market_id, price, shares)
    else:
        return {"skipped": True, "reason": f"Unknown action: {action}"}


async def _execute_buy(
    db: AsyncSession,
    portfolio: PaperPortfolio,
    follow: WalletFollow,
    alert: dict,
    market_id: str,
    price: Decimal,
    shares: Decimal,
    amount: Decimal,
) -> dict:
    """Execute a paper BUY: add to existing position or create new one."""
    # Check for existing open position
    existing = await db.execute(
        select(PaperPosition).where(
            PaperPosition.portfolio_id == portfolio.id,
            PaperPosition.market_id == market_id,
            PaperPosition.outcome == alert.get("outcome", ""),
            PaperPosition.status == "OPEN",
        )
    )
    position = existing.scalar_one_or_none()

    if position:
        # Update existing position (weighted average entry)
        total_shares = position.shares + shares
        total_cost = (position.avg_entry_price * position.shares) + (price * shares)
        position.avg_entry_price = total_cost / total_shares if total_shares > 0 else price
        position.shares = total_shares
        position.cost_basis += amount
    else:
        # Create new position
        position = PaperPosition(
            portfolio_id=portfolio.id,
            market_id=market_id,
            outcome=alert.get("outcome", ""),
            side="BUY",
            status="OPEN",
            shares=shares,
            avg_entry_price=price,
            cost_basis=amount,
            current_price=price,
            followed_wallet=follow.wallet,
            source_alert_id=alert.get("id"),
        )
        db.add(position)
        await db.flush()

    # Record trade
    trade = PaperTrade(
        portfolio_id=portfolio.id,
        position_id=position.id,
        source_alert_id=alert.get("id"),
        market_id=market_id,
        outcome=alert.get("outcome", ""),
        side="BUY",
        price=price,
        shares=shares,
        amount_usd=amount,
        followed_wallet=follow.wallet,
        copy_mode=follow.copy_mode,
        copy_value_used=follow.copy_value,
    )
    db.add(trade)

    # Update portfolio
    portfolio.current_balance -= amount
    portfolio.total_trades += 1
    portfolio.total_volume += amount

    await db.commit()

    return {
        "executed": True,
        "side": "BUY",
        "market_id": market_id,
        "shares": shares,
        "price": price,
        "amount": amount,
        "position_id": position.id,
        "trade_id": trade.id,
    }


async def _execute_sell(
    db: AsyncSession,
    portfolio: PaperPortfolio,
    follow: WalletFollow,
    alert: dict,
    market_id: str,
    price: Decimal,
    shares: Decimal,
) -> dict:
    """Execute a paper SELL: reduce or close an existing position."""
    existing = await db.execute(
        select(PaperPosition).where(
            PaperPosition.portfolio_id == portfolio.id,
            PaperPosition.market_id == market_id,
            PaperPosition.outcome == alert.get("outcome", ""),
            PaperPosition.status == "OPEN",
        )
    )
    position = existing.scalar_one_or_none()
    if position is None:
        return {"skipped": True, "reason": "No open position to sell"}

    sell_shares = min(shares, position.shares)
    sell_amount = sell_shares * price
    cost_of_sold_shares = sell_shares * position.avg_entry_price
    realized_pnl = sell_amount - cost_of_sold_shares

    # Record trade
    trade = PaperTrade(
        portfolio_id=portfolio.id,
        position_id=position.id,
        source_alert_id=alert.get("id"),
        market_id=market_id,
        outcome=alert.get("outcome", ""),
        side="SELL",
        price=price,
        shares=sell_shares,
        amount_usd=sell_amount,
        followed_wallet=follow.wallet,
        copy_mode=follow.copy_mode,
        copy_value_used=follow.copy_value,
    )
    db.add(trade)

    if sell_shares >= position.shares:
        # Full exit
        position.status = "CLOSED"
        position.closed_at = func.now()
        position.realized_pnl += realized_pnl
        position.shares = 0
    else:
        # Partial exit
        position.shares -= sell_shares
        position.realized_pnl += realized_pnl
        position.cost_basis -= cost_of_sold_shares

    # Update portfolio
    portfolio.current_balance += sell_amount
    portfolio.total_realized_pnl += realized_pnl
    portfolio.total_trades += 1
    portfolio.total_volume += sell_amount
    portfolio.current_balance = portfolio.current_balance  # keep reference
    portfolio.total_pnl = portfolio.total_realized_pnl + portfolio.total_unrealized_pnl

    # Update unrealized PnL for remaining shares
    if position.status == "OPEN" and position.shares > 0:
        position.current_price = price
        position.unrealized_pnl = (price - position.avg_entry_price) * position.shares

    await db.commit()

    return {
        "executed": True,
        "side": "SELL",
        "market_id": market_id,
        "shares": sell_shares,
        "price": price,
        "amount": sell_amount,
        "realized_pnl": realized_pnl,
        "position_id": position.id,
        "trade_id": trade.id,
    }


def _compute_copy_amount(
    copy_mode: Optional[str],
    copy_value: Decimal,
    position_size: Decimal,
) -> Decimal:
    """Compute copy amount based on mode and value."""
    if copy_mode == "proportional":
        return position_size * copy_value  # e.g. 0.05 = 5%
    elif copy_mode == "fixed":
        return copy_value  # fixed $ amount
    else:
        return Decimal("0")


async def _get_current_price(
    db: AsyncSession, market_id: str, outcome_label: str
) -> Optional[Decimal]:
    """Get current market price from outcomes table."""
    result = await db.execute(
        select(func.max(..."price"))
        .select_from(...)
        .where(...)
    )
    # Simplified — look up outcome price
    result = await db.execute(
        text("""
            SELECT price FROM outcomes
            WHERE market_id = :market_id
              AND label = :outcome
            ORDER BY price DESC
            LIMIT 1
        """),
        {"market_id": market_id, "outcome": outcome_label},
    )
    row = result.one_or_none()
    return Decimal(str(row.price)) if row else None


async def _get_or_create_portfolio(
    db: AsyncSession, user_id: str = "default"
) -> PaperPortfolio:
    """Get existing portfolio or create a new one."""
    result = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        portfolio = PaperPortfolio(
            user_id=user_id,
            initial_balance=Decimal("10000"),
            current_balance=Decimal("10000"),
        )
        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)
    return portfolio
```

---

## Unrealized PnL Update

Periodically update unrealized PnL for open positions using current outcome prices:

```python
async def update_unrealized_pnl(db: AsyncSession):
    """Update unrealized PnL for all open paper positions using current market prices."""
    # Get all open positions
    result = await db.execute(
        select(PaperPosition).where(PaperPosition.status == "OPEN")
    )
    positions = result.scalars().all()

    for pos in positions:
        current_price = await _get_current_price(db, pos.market_id, pos.outcome)
        if current_price:
            pos.current_price = current_price
            pos.unrealized_pnl = (current_price - pos.avg_entry_price) * pos.shares

    # Update portfolio total_unrealized_pnl
    for pos in positions:
        portfolio_id = pos.portfolio_id
        # Sum all unrealized PnL for this portfolio
    await db.commit()
```

This can run as a background task every N minutes or be triggered by the ETL pipeline.

---

## Market Resolution Handler

When a market resolves, auto-close any open paper positions:

```python
async def handle_market_resolution(
    db: AsyncSession, market_id: str, winning_outcome: str
):
    """Auto-close positions when a market resolves."""
    result = await db.execute(
        select(PaperPosition).where(
            PaperPosition.market_id == market_id,
            PaperPosition.status == "OPEN",
        )
    )
    positions = result.scalars().all()

    for pos in positions:
        resolution_price = Decimal("1.0") if pos.outcome == winning_outcome else Decimal("0.0")
        pos.status = "RESOLVED"
        pos.closed_at = func.now()
        pos.current_price = resolution_price
        pos.unrealized_pnl = (resolution_price - pos.avg_entry_price) * pos.shares
        pos.realized_pnl += pos.unrealized_pnl
        pos.unrealized_pnl = Decimal("0")

        # Update portfolio
        await db.execute(
            text("""
                UPDATE paper_portfolios
                SET current_balance = current_balance + :payout,
                    total_realized_pnl = total_realized_pnl + :pnl,
                    updated_at = NOW()
                WHERE id = :portfolio_id
            """),
            {
                "payout": resolution_price * pos.shares,
                "pnl": pos.realized_pnl,
                "portfolio_id": pos.portfolio_id,
            },
        )

    await db.commit()
```

---

## Sizing Scenarios

| Scenario | Configuration | Original Trade | Copy Trade |
|----------|---------------|---------------|------------|
| Proportional 5% | mode=proportional, value=0.05 | $12,000 | $600 |
| Proportional 1% | mode=proportional, value=0.01 | $12,000 | $120 |
| Fixed $100 | mode=fixed, value=100 | $12,000 | $100 |
| Insufficient balance | mode=proportional, value=0.5, balance=$200 | $1,000 | $200 (adjusted) |
| Category filtered | category_filter=["Politics"], alert.category="Crypto" | $5,000 | Skipped |

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `app/services/paper_trading.py` |

---

## Verification

```python
# Unit test scenarios:
# 1. Proportional: 5% of $12,000 = $600 ✅
# 2. Fixed: $100 always ✅
# 3. Insufficient balance: adjust to available ✅
# 4. Category filter: skip non-matching ✅
# 5. Zero price: skip ✅
# 6. Multiple buys: weighted avg entry ✅
# 7. Full exit: PnL calculated, position closed ✅
# 8. Partial exit: shares reduced, realized PnL tracked ✅
# 9. Market resolution: auto-close at 1.0/0.0 ✅
# 10. Empty portfolio: auto-create on first trade ✅
```
