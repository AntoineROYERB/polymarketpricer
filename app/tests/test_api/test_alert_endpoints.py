"""Unit tests for alert API endpoints."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.api.dependencies import get_db
from app.main import app


@pytest.mark.asyncio
async def test_alerts_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"] == []
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_alerts_with_limit(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10


@pytest.mark.asyncio
async def test_alerts_invalid_limit(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts?limit=999")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_alerts_negative_offset(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts?offset=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_alerts_invalid_offset_type(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts?offset=abc")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_alerts_category_filter(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts?category=politics")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_alerts_min_score_filter(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts?min_score=50")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_alerts_wallet_filter(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts?wallet=0xabcd")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_alerts_filters_combined(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/alerts?category=politics&min_score=50&limit=5"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 5


@pytest.mark.asyncio
async def test_alerts_wallet_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts/0xnonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_alerts_wallet_zero_alerts(client: AsyncClient) -> None:
    mock_session = AsyncMock()

    wallet_result = MagicMock()
    wallet_result.scalar_one_or_none.return_value = MagicMock()

    alert_result = MagicMock()
    alert_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock()
    mock_session.execute.side_effect = [wallet_result, alert_result]

    async def _override() -> AsyncMock:  # type: ignore[misc]
        yield mock_session

    original = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override
    try:
        response = await client.get("/api/v1/alerts/0xknownwallet")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
    finally:
        if original:
            app.dependency_overrides[get_db] = original
        else:
            del app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_alerts_stats_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_alerts"] == 0
    assert data["alerts_today"] == 0
    assert data["top_categories"] == []
    assert data["top_wallets"] == []


@pytest.mark.asyncio
async def test_alerts_stats_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_alerts" in data
    assert "alerts_today" in data
    assert "top_categories" in data
    assert "top_wallets" in data
