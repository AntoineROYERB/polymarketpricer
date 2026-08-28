import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_leaderboard_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["limit"] == 100
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_leaderboard_with_params(client: AsyncClient) -> None:
    response = await client.get("/api/v1/leaderboard?limit=10&offset=5")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 5


@pytest.mark.asyncio
async def test_leaderboard_emerging(client: AsyncClient) -> None:
    response = await client.get("/api/v1/leaderboard/emerging")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_leaderboard_consistent(client: AsyncClient) -> None:
    response = await client.get("/api/v1/leaderboard/consistent")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_wallet_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/wallets/0xnonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_markets_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/markets")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_markets_with_category(client: AsyncClient) -> None:
    response = await client.get("/api/v1/markets?category=politics")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_markets_unknown_category_returns_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/markets?category=not-a-category")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_markets_response_carries_total(client: AsyncClient) -> None:
    response = await client.get("/api/v1/markets")
    assert response.status_code == 200
    assert "total" in response.json()


@pytest.mark.asyncio
async def test_markets_accepts_search(client: AsyncClient) -> None:
    response = await client.get("/api/v1/markets?search=bitcoin")
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("sort", ["volume", "liquidity", "recent"])
async def test_markets_accepts_known_sorts(client: AsyncClient, sort: str) -> None:
    response = await client.get(f"/api/v1/markets?sort={sort}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_markets_rejects_unknown_sort(client: AsyncClient) -> None:
    response = await client.get("/api/v1/markets?sort=bogus")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_market_summary_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/markets?limit=1")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    if data["data"]:
        market = data["data"][0]
        assert "volume_usd" in market
        assert "winning_outcome" in market
        assert "close_time" in market


@pytest.mark.asyncio
async def test_get_wallet_profile_success(client: AsyncClient) -> None:
    """Test successful wallet profile response with mocked service layer."""
    from unittest.mock import patch

    mock_profile = {
        "wallet": "0x1234",
        "proxy_wallet": None,
        "label": "Test Wallet",
        "is_tracked": True,
        "first_seen": "2026-01-01T00:00:00Z",
        "last_seen": "2026-06-01T00:00:00Z",
    }
    from unittest.mock import MagicMock
    mock_analytics = MagicMock()
    mock_analytics.total_pnl = 50000.0
    mock_analytics.roi = 0.25
    mock_analytics.win_rate = 0.65
    mock_analytics.num_trades = 120
    mock_analytics.wallet_score = 85.5
    mock_analytics.avg_holding_duration = None
    mock_analytics.total_volume = 100000.0
    mock_analytics.avg_position_size = 500.0
    mock_analytics.sharpe_ratio = 1.5
    mock_analytics.profit_factor = 2.0
    mock_analytics.max_drawdown = -0.15
    mock_analytics.consistency_score = 0.8
    mock_analytics.experience_score = 0.7
    mock_positions: list[object] = []

    with (
        patch("app.api.v1.wallets.get_wallet_profile", return_value=mock_profile),
        patch("app.api.v1.wallets.get_wallet_analytics", return_value=mock_analytics),
        patch("app.api.v1.wallets.get_wallet_positions", return_value=mock_positions),
        patch("app.api.v1.wallets.get_wallet_categories_data", return_value=[]),
    ):
        response = await client.get("/api/v1/wallets/0x1234")
        assert response.status_code == 200
        data = response.json()
        assert data["wallet"] == "0x1234"
        assert data["analytics"]["total_pnl"] == 50000.0
        assert data["analytics"]["roi"] == 0.25
        assert data["analytics"]["num_trades"] == 120
        assert data["current_positions"] == []
