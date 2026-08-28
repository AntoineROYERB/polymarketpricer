"""Rate limiting must cover the routes mounted through include_router.

slowapi's own middleware resolves the route by reading ``endpoint`` off the
objects in ``app.routes``. FastAPI now represents an included router as a single
``_IncludedRouter`` with no such attribute, so the lookup returned None and every
``/api/v1/*`` route was treated as exempt — while ``/health`` stayed limited, which
made the gap invisible. These tests pin the behaviour to the API routes.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_db
from app.main import app, limiter
from app.tests.conftest import make_mock_session

LIMIT = 60


@pytest.fixture
def rate_limited_client() -> Iterator[TestClient]:
    mock_session = make_mock_session()

    def override_get_db() -> Iterator[object]:
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    limiter.reset()
    try:
        yield TestClient(app)
    finally:
        limiter.reset()
        app.dependency_overrides.clear()


def _first_429(client: TestClient, path: str, attempts: int) -> int | None:
    for i in range(1, attempts + 1):
        if client.get(path).status_code == 429:
            return i
    return None


@pytest.mark.parametrize(
    "path",
    ["/api/v1/leaderboard", "/api/v1/markets", "/api/v1/alerts/stats"],
)
def test_api_routes_are_rate_limited(rate_limited_client: TestClient, path: str) -> None:
    assert _first_429(rate_limited_client, path, LIMIT + 5) == LIMIT + 1


def test_limit_is_per_path(rate_limited_client: TestClient) -> None:
    """Exhausting one route must not lock out an unrelated one."""
    assert _first_429(rate_limited_client, "/api/v1/leaderboard", LIMIT + 5) is not None
    assert rate_limited_client.get("/api/v1/markets").status_code == 200


def test_health_is_exempt(rate_limited_client: TestClient) -> None:
    """Container health probes must never be throttled."""
    assert _first_429(rate_limited_client, "/health", LIMIT + 5) is None
