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
