from collections.abc import AsyncIterator

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_db
from app.main import app


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    mock_result.all.return_value = []

    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
async def client(mock_session: AsyncMock) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncMock]:
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestEdgeLeaderboard:
    async def test_edge_leaderboard_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/leaderboard/edge?limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["limit"] == 5
        assert body["offset"] == 0

    async def test_edge_leaderboard_with_data(self, client: AsyncClient, mock_session: AsyncMock) -> None:
        mock_wallet = MagicMock()
        mock_wallet.wallet = "0xwallet1"
        mock_wallet.edge_score = Decimal("0.95")
        mock_wallet.avg_edge = Decimal("0.42")
        mock_wallet.edge_consistency = Decimal("0.78")
        mock_wallet.num_edge_trades = 34

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_wallet]
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = await client.get("/api/v1/leaderboard/edge?limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        entry = body["data"][0]
        assert entry["wallet"] == "0xwallet1"
        assert entry["edge_score"] == "0.95"
        assert entry["rank"] == 1

    async def test_edge_leaderboard_pagination(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/leaderboard/edge?limit=10&offset=20")
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 10
        assert body["offset"] == 20

    async def test_edge_leaderboard_invalid_limit(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/leaderboard/edge?limit=999")
        assert resp.status_code == 422


class TestWalletEdge:
    async def test_wallet_edge_success(self, client: AsyncClient, mock_session: AsyncMock) -> None:
        mock_wallet_row = MagicMock()
        mock_wallet_row.wallet = "0xwallet1"
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_wallet_row)))

        mock_snapshot = MagicMock()
        mock_snapshot.wallet = "0xwallet1"
        mock_snapshot.snapshot_date = None
        mock_snapshot.avg_edge = Decimal("0")
        mock_snapshot.median_edge = None
        mock_snapshot.edge_consistency = None
        mock_snapshot.edge_volatility = None
        mock_snapshot.edge_score = None
        mock_snapshot.num_edge_trades = 0
        mock_snapshot.positive_edge_trades = None
        mock_snapshot.negative_edge_trades = None
        mock_snapshot.computed_at = None

        mock_edge_result = MagicMock()
        mock_edge_result.scalar_one_or_none.return_value = mock_snapshot

        def execute_side_effect(*args: object, **kwargs: object) -> MagicMock:
            return mock_edge_result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        resp = await client.get("/api/v1/wallets/0xwallet1/edge")
        assert resp.status_code == 200

    async def test_wallet_edge_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/wallets/0xnonexistent/edge")
        assert resp.status_code == 404
