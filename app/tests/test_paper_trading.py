"""Unit tests for paper trading engine (pure functions + mocked DB)."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_follow import PaperPortfolio, WalletFollow
from app.services.paper_trading import (
    _compute_copy_amount,
    execute_copy_trade,
    handle_market_resolution,
    update_unrealized_pnl,
)


def make_follow(**overrides: Any) -> WalletFollow:
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "wallet": "0xwallet",
        "user_id": "default",
        "label": "Test",
        "active": True,
        "auto_copy_enabled": True,
        "copy_mode": "proportional",
        "copy_value": Decimal("0.05"),
        "category_filter": None,
        "followed_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return WalletFollow(**defaults)


def make_portfolio(**overrides: Any) -> PaperPortfolio:
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "user_id": "default",
        "name": "Main",
        "initial_balance": Decimal(10000),
        "current_balance": Decimal(10000),
        "total_realized_pnl": Decimal(0),
        "total_unrealized_pnl": Decimal(0),
        "total_pnl": Decimal(0),
        "total_roi": None,
        "total_trades": 0,
        "total_volume": Decimal(0),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return PaperPortfolio(**defaults)


def make_mock_db() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_scalars.one_or_none.return_value = None

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    mock_result.all.return_value = []

    mock_result.one_or_none.return_value = None

    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    return session


class TestComputeCopyAmount:
    def test_proportional_5_percent(self) -> None:
        amount = _compute_copy_amount("proportional", Decimal("0.05"), Decimal(12000))
        assert amount == Decimal(600)

    def test_proportional_1_percent(self) -> None:
        amount = _compute_copy_amount("proportional", Decimal("0.01"), Decimal(12000))
        assert amount == Decimal(120)

    def test_fixed_100(self) -> None:
        amount = _compute_copy_amount("fixed", Decimal(100), Decimal(12000))
        assert amount == Decimal(100)

    def test_fixed_500(self) -> None:
        amount = _compute_copy_amount("fixed", Decimal(500), Decimal(12000))
        assert amount == Decimal(500)

    def test_unknown_mode_returns_zero(self) -> None:
        amount = _compute_copy_amount("unknown", Decimal(100), Decimal(12000))
        assert amount == Decimal(0)

    def test_none_mode_returns_zero(self) -> None:
        amount = _compute_copy_amount(None, Decimal(100), Decimal(12000))
        assert amount == Decimal(0)

    def test_zero_position_size(self) -> None:
        amount = _compute_copy_amount("proportional", Decimal("0.05"), Decimal(0))
        assert amount == Decimal(0)

    def test_large_value(self) -> None:
        amount = _compute_copy_amount("proportional", Decimal(1), Decimal(1000000))
        assert amount == Decimal(1000000)


class TestExecuteCopyTradeSkipped:
    @pytest.mark.asyncio
    async def test_category_filter_exclude(self) -> None:
        follow = make_follow(category_filter=["Politics", "Sports"])
        db = make_mock_db()
        alert = {"category": "Crypto", "position_size": 1000, "market_id": "m1"}
        result = await execute_copy_trade(db, alert, follow)
        assert result is not None
        assert result["skipped"] is True
        assert "filtered out" in result["reason"]

    @pytest.mark.asyncio
    async def test_zero_position_size(self) -> None:
        follow = make_follow()
        db = make_mock_db()
        alert = {"position_size": 0}
        result = await execute_copy_trade(db, alert, follow)
        assert result is not None
        assert result["skipped"] is True
        assert "Zero position size" in result["reason"]

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        follow = make_follow()
        db = make_mock_db()
        alert = {"position_size": 1000, "action": "UNKNOWN"}
        result = await execute_copy_trade(db, alert, follow)
        assert result is not None
        assert result["skipped"] is True

    @pytest.mark.asyncio
    async def test_category_filter_include_skipped_by_price(self) -> None:
        """When category matches filter, should proceed past filter (but skipped by price)."""
        follow = make_follow(category_filter=["Crypto"])
        db = make_mock_db()
        alert = {"category": "Crypto", "position_size": 1000, "market_id": "m1"}
        result = await execute_copy_trade(db, alert, follow)
        assert result is not None
        assert result["skipped"] is True
        assert "price" in result["reason"].lower()


class TestHandleMarketResolution:
    @pytest.mark.asyncio
    async def test_no_open_positions(self) -> None:
        db = make_mock_db()
        await handle_market_resolution(db, "market123", "Yes")
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()


class TestUpdateUnrealizedPnl:
    @pytest.mark.asyncio
    async def test_no_open_positions(self) -> None:
        db = make_mock_db()
        await update_unrealized_pnl(db)
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()
