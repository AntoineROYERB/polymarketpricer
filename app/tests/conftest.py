from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_db
from app.main import app


def make_mock_session() -> AsyncMock:
    session = AsyncMock()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    mock_result.all.return_value = []

    session.execute = AsyncMock(return_value=mock_result)

    return session


def make_mock_category_analytic(**kwargs: Any) -> MagicMock:
    row = MagicMock()
    row.wallet = kwargs.get("wallet", "0xmockwallet")
    row.category = kwargs.get("category", "Politics")
    row.num_trades = kwargs.get("num_trades", 50)
    row.total_volume = kwargs.get("total_volume", 25000.0)
    row.total_cost_basis = kwargs.get("total_cost_basis", 20000.0)
    row.total_pnl = kwargs.get("total_pnl", 5000.0)
    row.total_realized_pnl = kwargs.get("total_realized_pnl", 3000.0)
    row.total_unrealized_pnl = kwargs.get("total_unrealized_pnl", 2000.0)
    row.roi = kwargs.get("roi", 25.0)
    row.win_rate = kwargs.get("win_rate", 0.7)
    row.num_resolved_positions = kwargs.get("num_resolved_positions", 20)
    row.profit_factor = kwargs.get("profit_factor", 1.5)
    row.avg_position_size = kwargs.get("avg_position_size", 500.0)
    row.avg_holding_duration = kwargs.get("avg_holding_duration", "7 days")
    row.is_specialist = kwargs.get("is_specialist", True)
    row.category_rank = kwargs.get("category_rank", 5)
    return row


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    mock_session = make_mock_session()

    async def override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
