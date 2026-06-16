from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_leaderboard_empty(client: AsyncClient):
    response = await client.get("/api/v1/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["limit"] == 100
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_leaderboard_with_params(client: AsyncClient):
    response = await client.get("/api/v1/leaderboard?limit=10&offset=5")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 5


@pytest.mark.asyncio
async def test_leaderboard_emerging(client: AsyncClient):
    response = await client.get("/api/v1/leaderboard/emerging")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_leaderboard_consistent(client: AsyncClient):
    response = await client.get("/api/v1/leaderboard/consistent")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_wallet_not_found(client: AsyncClient):
    response = await client.get("/api/v1/wallets/0xnonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_markets_empty(client: AsyncClient):
    response = await client.get("/api/v1/markets")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_markets_with_category(client: AsyncClient):
    response = await client.get("/api/v1/markets?category=politics")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
