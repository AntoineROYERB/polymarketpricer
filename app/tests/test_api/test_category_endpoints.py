from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.tests.conftest import make_mock_category_analytic


@pytest.mark.asyncio
async def test_category_leaderboard_valid(client: AsyncClient) -> None:
    response = await client.get("/api/v1/leaderboard/politics")
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "politics"
    assert "data" in data
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_category_leaderboard_invalid_category(client: AsyncClient) -> None:
    response = await client.get("/api/v1/leaderboard/invalid")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_category_leaderboard_with_params(client: AsyncClient) -> None:
    response = await client.get("/api/v1/leaderboard/crypto?limit=10&offset=5")
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "crypto"
    assert data["limit"] == 10
    assert data["offset"] == 5


@pytest.mark.asyncio
async def test_category_specialists(client: AsyncClient) -> None:
    response = await client.get("/api/v1/leaderboard/crypto/specialists")
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "crypto"
    assert "data" in data


@pytest.mark.asyncio
@patch("app.api.v1.categories.wallet_exists", new_callable=AsyncMock)
@patch("app.api.v1.categories.get_wallet_categories_data", new_callable=AsyncMock)
async def test_wallet_categories(
    mock_get_categories: AsyncMock,
    mock_wallet_exists: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_wallet_exists.return_value = True
    mock_get_categories.return_value = [make_mock_category_analytic()]

    response = await client.get("/api/v1/wallets/0xabc/categories")
    assert response.status_code == 200
    data = response.json()
    assert data["wallet"] == "0xabc"
    assert len(data["categories"]) == 1
    cat = data["categories"][0]
    assert cat["category"] == "Politics"
    assert cat["num_trades"] == 50


@pytest.mark.asyncio
async def test_wallet_categories_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/wallets/0xnonexistent/categories")
    assert response.status_code == 404


@pytest.mark.asyncio
@patch("app.api.v1.categories.wallet_exists", new_callable=AsyncMock)
@patch("app.api.v1.categories.get_wallet_category_detail_data", new_callable=AsyncMock)
async def test_wallet_category_detail(
    mock_get_detail: AsyncMock,
    mock_wallet_exists: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_wallet_exists.return_value = True
    mock_get_detail.return_value = make_mock_category_analytic()

    response = await client.get("/api/v1/wallets/0xabc/categories/politics")
    assert response.status_code == 200
    data = response.json()
    assert data["wallet"] == "0xmockwallet"
    assert data["category"] == "Politics"
    assert "roi" in data
    assert "win_rate" in data


@pytest.mark.asyncio
@patch("app.api.v1.categories.wallet_exists", new_callable=AsyncMock)
async def test_wallet_category_detail_not_found(
    mock_wallet_exists: AsyncMock,
    client: AsyncClient,
) -> None:
    mock_wallet_exists.return_value = True

    response = await client.get("/api/v1/wallets/0xabc/categories/sports")
    assert response.status_code == 404
