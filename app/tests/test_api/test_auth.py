"""Test API key authentication."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_public_endpoint_no_auth(client: AsyncClient) -> None:
    """Leaderboard should not require auth."""
    response = await client.get("/api/v1/leaderboard")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_follow_with_valid_key(client: AsyncClient) -> None:
    """Valid API key should not be rejected."""
    response = await client.get(
        "/api/v1/follow",
        headers={"Authorization": "Bearer devkey-change-me"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_follow_with_any_key(client: AsyncClient) -> None:
    """optional_api_key never rejects — invalid keys fall back to 'default'."""
    response = await client.get(
        "/api/v1/follow",
        headers={"Authorization": "Bearer any-key-works"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_follow_without_auth_defaults_to_default(client: AsyncClient) -> None:
    """Missing auth should return 200 (optional_api_key defaults to 'default')."""
    response = await client.get("/api/v1/follow")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_portfolio_with_valid_key(client: AsyncClient) -> None:
    """Valid key on portfolio endpoint."""
    response = await client.get(
        "/api/v1/portfolio",
        headers={"Authorization": "Bearer devkey-change-me"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_portfolio_without_auth(client: AsyncClient) -> None:
    """Portfolio works without auth (falls back to 'default')."""
    response = await client.get("/api/v1/portfolio")
    assert response.status_code == 200


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
