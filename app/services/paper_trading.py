"""Paper trading engine — simulates copy trades from followed wallets."""

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    WalletFollow, PaperPortfolio, PaperPosition, PaperTrade,
)


async def execute_copy_trade(
    db: AsyncSession,
    alert: dict,
    follow: WalletFollow,
) -> Optional[dict]:
    """Execute a paper copy trade based on an alert and follow config."""
    if follow.category_filter:
        alert_category = alert.get("category", "")
        if alert_category not in follow.category_filter:
            return {"skipped": True, "reason": f"Category '{alert_category}' filtered out"}

    portfolio = await _get_or_create_portfolio(db, follow.user_id)

    position_size = Decimal(str(alert.get("position_size", 0)))
    if position_size <= 0:
        return {"skipped": True, "reason": "Zero position size"}

    copy_amount = _compute_copy_amount(follow.copy_mode, follow.copy_value, position_size)

    if copy_amount > portfolio.current_balance:
        copy_amount = portfolio.current_balance
        if copy_amount <= 0:
            return {"skipped": True, "reason": "Insufficient balance"}

    market_id = alert.get("market_id", "")
    price = await _get_current_price(db, market_id, alert.get("outcome", "Yes"))
    if price is None or price <= 0:
        return {"skipped": True, "reason": "Market price unavailable"}

    action = alert.get("action", "")
    side = "BUY" if action in ("NEW_POSITION", "POSITION_INCREASE", "TRADE_BUY") else "SELL"

    if side == "BUY":
        shares = copy_amount / price if price > 0 else Decimal("0")
        return await _execute_buy(db, portfolio, follow, alert, market_id, price, shares, copy_amount)
    elif side == "SELL":
        shares = Decimal(str(alert.get("shares", 0)))
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
    existing = await db.execute(
        select(PaperPosition).where(
            PaperPosition.portfolio_id == portfolio.id,
            PaperPosition.market_id == market_id,
            PaperPosition.outcome == alert.get("outcome", ""),
            PaperPosition.followed_wallet == follow.wallet,
            PaperPosition.status == "OPEN",
        ).with_for_update()
    )
    position = existing.scalar_one_or_none()

    if position:
        total_shares = position.shares + shares
        total_cost = (position.avg_entry_price * position.shares) + (price * shares)
        position.avg_entry_price = total_cost / total_shares if total_shares > 0 else price
        position.shares = total_shares
        position.cost_basis += amount
    else:
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
    existing = await db.execute(
        select(PaperPosition).where(
            PaperPosition.portfolio_id == portfolio.id,
            PaperPosition.market_id == market_id,
            PaperPosition.outcome == alert.get("outcome", ""),
            PaperPosition.followed_wallet == follow.wallet,
            PaperPosition.status == "OPEN",
        ).with_for_update()
    )
    position = existing.scalar_one_or_none()
    if position is None:
        return {"skipped": True, "reason": "No open position to sell"}

    sell_shares = min(shares, position.shares)
    sell_amount = sell_shares * price
    cost_of_sold_shares = sell_shares * position.avg_entry_price
    realized_pnl = sell_amount - cost_of_sold_shares

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
        position.status = "CLOSED"
        position.closed_at = func.now()
        position.realized_pnl += realized_pnl
        position.shares = Decimal("0")
    else:
        position.shares -= sell_shares
        position.realized_pnl += realized_pnl
        position.cost_basis -= cost_of_sold_shares

    portfolio.current_balance += sell_amount
    portfolio.total_realized_pnl += realized_pnl
    portfolio.total_trades += 1
    portfolio.total_volume += sell_amount
    portfolio.total_pnl = portfolio.total_realized_pnl + portfolio.total_unrealized_pnl

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
    if copy_mode == "proportional":
        return position_size * max(copy_value, Decimal("0"))
    elif copy_mode == "fixed":
        return max(copy_value, Decimal("0"))
    logger.warning("Unknown copy_mode '%s', returning 0", copy_mode)
    return Decimal("0")


async def _get_current_price(
    db: AsyncSession, market_id: str, outcome_label: str
) -> Optional[Decimal]:
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
    if row is None:
        return None
    price_val = row._mapping.get("price")
    if price_val is None:
        return None
    return Decimal(str(price_val))


async def _get_or_create_portfolio(
    db: AsyncSession, user_id: str = "default"
) -> PaperPortfolio:
    result = await db.execute(
        select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        portfolio = PaperPortfolio(
            user_id=user_id,
            name="Main",
            initial_balance=Decimal("10000"),
            current_balance=Decimal("10000"),
            total_realized_pnl=Decimal("0"),
            total_unrealized_pnl=Decimal("0"),
            total_pnl=Decimal("0"),
            total_trades=0,
            total_volume=Decimal("0"),
        )
        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)
    return portfolio


async def update_unrealized_pnl(db: AsyncSession) -> None:
    """Update unrealized PnL for all open paper positions using current market prices."""
    result = await db.execute(
        select(PaperPosition).where(PaperPosition.status == "OPEN")
    )
    positions = result.scalars().all()

    for pos in positions:
        current_price = await _get_current_price(db, pos.market_id, pos.outcome)
        if current_price:
            pos.current_price = current_price
            pos.unrealized_pnl = (current_price - pos.avg_entry_price) * pos.shares

    portfolio_totals: dict[UUID, Decimal] = {}
    for pos in positions:
        pid = pos.portfolio_id
        portfolio_totals[pid] = portfolio_totals.get(pid, Decimal("0")) + (pos.unrealized_pnl or Decimal("0"))

    for pid, unrealized in portfolio_totals.items():
        result = await db.execute(
            select(PaperPortfolio).where(PaperPortfolio.id == pid)
        )
        pf = result.scalar_one_or_none()
        if pf:
            pf.total_unrealized_pnl = unrealized
            pf.total_pnl = pf.total_realized_pnl + unrealized

    await db.commit()


async def handle_market_resolution(
    db: AsyncSession, market_id: str, winning_outcome: str
) -> None:
    """Auto-close positions when a market resolves."""
    result = await db.execute(
        select(PaperPosition).where(
            PaperPosition.market_id == market_id,
            PaperPosition.status == "OPEN",
        ).with_for_update()
    )
    positions = result.scalars().all()

    for pos in positions:
        resolution_price = Decimal("1.0") if pos.outcome == winning_outcome else Decimal("0.0")
        pos.status = "RESOLVED"
        pos.closed_at = func.now()
        pos.current_price = resolution_price
        pnl = (resolution_price - pos.avg_entry_price) * pos.shares
        pos.unrealized_pnl = Decimal("0")
        pos.realized_pnl += pnl

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
                "pnl": pnl,
                "portfolio_id": pos.portfolio_id,
            },
        )

    await db.commit()
