import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_recommendations_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/follow/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "limit" in data


@pytest.mark.asyncio
async def test_recommendations_by_category_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/follow/recommendations/by-category/politics")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_recommendations_by_invalid_category(client: AsyncClient) -> None:
    response = await client.get("/api/v1/follow/recommendations/by-category/invalid")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_wallet_recommendations_by_category(client: AsyncClient) -> None:
    response = await client.get("/api/v1/follow/recommendations/0xtest/by-category")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_follow_unknown_wallet(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/follow/0xdeadbeef00000000000000000000000000000001",
        json={},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_follows(client: AsyncClient) -> None:
    response = await client.get("/api/v1/follow")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_follow_duplicate(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/follow/0xdeadbeef00000000000000000000000000000002",
        json={},
    )
    assert response.status_code in (201, 404, 409)


@pytest.mark.asyncio
async def test_unfollow_not_found(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/follow/0xdeadbeef00000000000000000000000000000003")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_follow_not_found(client: AsyncClient) -> None:
    response = await client.patch(
        "/api/v1/follow/0xdeadbeef00000000000000000000000000000003",
        json={"label": "test"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_follow_rejects_malformed_wallet(client: AsyncClient) -> None:
    """A 0x prefix alone is not an address; the route must not accept one."""
    response = await client.post("/api/v1/follow/0xdeadbeef", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unfollow_rejects_malformed_wallet(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/follow/not-an-address")
    assert response.status_code == 422
