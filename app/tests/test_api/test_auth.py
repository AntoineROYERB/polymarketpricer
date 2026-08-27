"""Test API key authentication."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_db
from app.main import app
from app.tests.conftest import make_mock_session


@pytest.fixture
async def raw_client() -> AsyncGenerator[AsyncClient, None]:
    """Client with no auth override, to exercise require_api_key for real."""
    mock_session = make_mock_session()

    async def override_get_db() -> AsyncGenerator[object, None]:
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_endpoint_no_auth(client: AsyncClient) -> None:
    """Leaderboard should not require auth."""
    response = await client.get("/api/v1/leaderboard")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_follow_with_valid_key(raw_client: AsyncClient) -> None:
    response = await raw_client.get(
        "/api/v1/follow",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_follow_with_invalid_key_rejected(raw_client: AsyncClient) -> None:
    response = await raw_client.get(
        "/api/v1/follow",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_follow_without_auth_rejected(raw_client: AsyncClient) -> None:
    response = await raw_client.get("/api/v1/follow")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_with_valid_key(raw_client: AsyncClient) -> None:
    response = await raw_client.get(
        "/api/v1/portfolio",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_portfolio_without_auth_rejected(raw_client: AsyncClient) -> None:
    response = await raw_client.get("/api/v1/portfolio")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cors_preflight(client: AsyncClient) -> None:
    """CORS preflight should return 200."""
    response = await client.options(
        "/api/v1/leaderboard",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
