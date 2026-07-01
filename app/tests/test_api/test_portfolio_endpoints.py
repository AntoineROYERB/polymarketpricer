import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_portfolio_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert "current_balance" in data


@pytest.mark.asyncio
async def test_list_positions_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/positions")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_list_trades_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/portfolio/trades")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_close_invalid_position(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/portfolio/positions/00000000-0000-0000-0000-000000000000/close"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reset_portfolio_empty(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/portfolio/reset",
        json={"initial_balance": 50000},
    )
    assert response.status_code == 200
    data = response.json()
    assert "portfolio" in data
    assert "message" in data
