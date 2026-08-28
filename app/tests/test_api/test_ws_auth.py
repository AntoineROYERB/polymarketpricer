"""The alert WebSocket must reject unauthenticated connections.

A missing key used to be waved through: the check only fired when a key was
present but wrong, so any non-browser client could attach to the stream.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


@pytest.fixture
def ws_client() -> TestClient:
    return TestClient(app)


def test_ws_without_key_rejected(ws_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_client.websocket_connect("/api/v1/alerts/ws"):
            pass
    assert exc.value.code == 4001


def test_ws_with_wrong_key_rejected(ws_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_client.websocket_connect("/api/v1/alerts/ws?api_key=wrong-key"):
            pass
    assert exc.value.code == 4001


def test_ws_with_empty_key_rejected(ws_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_client.websocket_connect("/api/v1/alerts/ws?api_key="):
            pass
    assert exc.value.code == 4001


def test_ws_with_valid_key_accepted(ws_client: TestClient) -> None:
    with ws_client.websocket_connect("/api/v1/alerts/ws?api_key=test-key") as ws:
        assert ws is not None


def test_ws_valid_key_but_foreign_origin_rejected(ws_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_client.websocket_connect(
            "/api/v1/alerts/ws?api_key=test-key",
            headers={"Origin": "https://evil.example"},
        ):
            pass
    assert exc.value.code == 4001
