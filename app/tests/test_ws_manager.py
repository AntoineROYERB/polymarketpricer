"""Unit tests for WebSocket connection manager."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import Alert
from app.services.ws_manager import ConnectionManager


@pytest.fixture
def manager() -> ConnectionManager:
    return ConnectionManager()


@pytest.fixture
def mock_ws() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def sample_alert() -> MagicMock:
    alert = MagicMock(spec=Alert)
    alert.id = "abc-123-def"
    alert.wallet = "0x1234567890abcdef1234567890abcdef12345678"
    alert.market_id = "market_001"
    alert.market_question = "Will BTC reach $100k?"
    alert.action = "NEW_POSITION"
    alert.price = 0.75
    alert.position_size = 5000.00
    alert.wallet_score = 85.5
    alert.category = "crypto"
    alert.detected_at = MagicMock()
    alert.detected_at.isoformat.return_value = "2026-06-24T12:00:00+00:00"
    return alert


# ===========================================================================
# connect / disconnect
# ===========================================================================

class TestConnectionLifecycle:
    @pytest.mark.asyncio
    async def test_connect_adds_connection(self, manager: ConnectionManager, mock_ws: AsyncMock) -> None:
        await manager.connect(mock_ws)
        assert len(manager.active_connections) == 1
        assert manager.active_connections[0] is mock_ws

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, manager: ConnectionManager, mock_ws: AsyncMock) -> None:
        await manager.connect(mock_ws)
        mock_ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager: ConnectionManager, mock_ws: AsyncMock) -> None:
        await manager.connect(mock_ws)
        assert len(manager.active_connections) == 1

        manager.disconnect(mock_ws)
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_disconnect_unknown_ws_does_not_raise(self, manager: ConnectionManager) -> None:
        manager.disconnect("not-in-list")  # type: ignore[arg-type]
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_multiple_connections(self, manager: ConnectionManager) -> None:
        ws1, ws2, ws3 = AsyncMock(), AsyncMock(), AsyncMock()
        for ws in (ws1, ws2, ws3):
            await manager.connect(ws)
        assert len(manager.active_connections) == 3

        manager.disconnect(ws2)
        assert len(manager.active_connections) == 2
        assert manager.active_connections == [ws1, ws3]


# ===========================================================================
# broadcast_alert
# ===========================================================================

class TestBroadcastAlert:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(
        self, manager: ConnectionManager, sample_alert: MagicMock,
    ) -> None:
        ws1, ws2 = AsyncMock(), AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)

        await manager.broadcast_alert(sample_alert)

        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_payload_structure(
        self, manager: ConnectionManager, sample_alert: MagicMock,
    ) -> None:
        ws = AsyncMock()
        await manager.connect(ws)
        await manager.broadcast_alert(sample_alert)

        sent_payload = ws.send_json.call_args[0][0]
        assert sent_payload["type"] == "alert"
        assert "payload" in sent_payload

        p = sent_payload["payload"]
        assert p["id"] == str(sample_alert.id)
        assert p["wallet"] == sample_alert.wallet
        assert p["market_id"] == sample_alert.market_id
        assert p["market_question"] == sample_alert.market_question
        assert p["action"] == sample_alert.action
        assert p["price"] == float(sample_alert.price)
        assert p["position_size"] == float(sample_alert.position_size)
        assert p["wallet_score"] == float(sample_alert.wallet_score)
        assert p["category"] == sample_alert.category
        assert p["detected_at"] == sample_alert.detected_at.isoformat()

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connection(
        self, manager: ConnectionManager, sample_alert: MagicMock,
    ) -> None:
        ws1 = AsyncMock()  # healthy
        ws2 = AsyncMock()  # dead
        ws2.send_json.side_effect = Exception("WebSocket disconnected")

        await manager.connect(ws1)
        await manager.connect(ws2)
        assert len(manager.active_connections) == 2

        await manager.broadcast_alert(sample_alert)

        # Dead connection should be removed
        assert len(manager.active_connections) == 1
        assert manager.active_connections[0] is ws1

    @pytest.mark.asyncio
    async def test_broadcast_with_no_connections(
        self, manager: ConnectionManager, sample_alert: MagicMock,
    ) -> None:
        await manager.broadcast_alert(sample_alert)  # should not raise
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_partial_failure_leaves_healthy(
        self, manager: ConnectionManager, sample_alert: MagicMock,
    ) -> None:
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws2.send_json.side_effect = Exception("gone")
        ws3 = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.connect(ws3)

        await manager.broadcast_alert(sample_alert)

        # ws2 removed, ws1 and ws3 remain
        assert len(manager.active_connections) == 2
        assert ws1 in manager.active_connections
        assert ws3 in manager.active_connections

        ws1.send_json.assert_awaited_once()
        ws3.send_json.assert_awaited_once()


# ===========================================================================
# heartbeat
# ===========================================================================

class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_sends_ping(self, manager: ConnectionManager) -> None:
        ws = AsyncMock()
        await manager.connect(ws)
        await manager.send_heartbeat()
        ws.send_json.assert_awaited_once_with({"type": "ping"})

    @pytest.mark.asyncio
    async def test_heartbeat_to_all(self, manager: ConnectionManager) -> None:
        ws1, ws2 = AsyncMock(), AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.send_heartbeat()
        ws1.send_json.assert_awaited_once_with({"type": "ping"})
        ws2.send_json.assert_awaited_once_with({"type": "ping"})

    @pytest.mark.asyncio
    async def test_heartbeat_removes_dead_connections(self, manager: ConnectionManager) -> None:
        live = AsyncMock()
        dead = AsyncMock()
        dead.send_json.side_effect = Exception("disconnected")

        await manager.connect(live)
        await manager.connect(dead)
        assert len(manager.active_connections) == 2

        await manager.send_heartbeat()

        assert len(manager.active_connections) == 1
        assert manager.active_connections[0] is live

    @pytest.mark.asyncio
    async def test_heartbeat_no_connections(self, manager: ConnectionManager) -> None:
        await manager.send_heartbeat()  # should not raise
