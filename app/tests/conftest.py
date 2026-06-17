from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_db
from app.main import app


def make_mock_session() -> AsyncMock:
    session = AsyncMock()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    mock_result.all.return_value = []

    session.execute = AsyncMock(return_value=mock_result)

    return session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    mock_session = make_mock_session()

    async def override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
