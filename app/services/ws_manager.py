from collections.abc import Awaitable, Callable
from typing import Any, Optional

from fastapi import WebSocket

from app.db.models import Alert


MAX_WS_CONNECTIONS = 100


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        if len(self.active_connections) >= MAX_WS_CONNECTIONS:
            await websocket.close(code=1013)
            return
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def _broadcast(self, send_fn: Callable[[WebSocket], Awaitable[None]]) -> None:
        dead = []
        for conn in self.active_connections:
            try:
                await send_fn(conn)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)

    async def broadcast_alert(
        self,
        alert: Alert,
        follow_info: Optional[dict[str, Any]] = None,
        copy_suggestion: Optional[dict[str, Any]] = None,
    ) -> None:
        payload: dict[str, Any] = {
            "type": "alert",
            "payload": {
                "id": str(alert.id),
                "wallet": alert.wallet,
                "market_id": alert.market_id,
                "market_question": alert.market_question,
                "action": alert.action,
                "price": float(alert.price),
                "position_size": float(alert.position_size),
                "wallet_score": float(alert.wallet_score),
                "category": alert.category,
                "detected_at": alert.detected_at.isoformat(),
            },
        }
        if follow_info:
            payload["payload"]["follow_info"] = {
                "label": follow_info.get("label"),
                "followed_at": follow_info["followed_at"].isoformat() if follow_info.get("followed_at") else None,
            }
        if copy_suggestion:
            payload["payload"]["copy_suggestion"] = copy_suggestion
        await self._broadcast(lambda conn: conn.send_json(payload))

    async def send_heartbeat(self) -> None:
        await self._broadcast(lambda conn: conn.send_json({"type": "ping"}))


manager = ConnectionManager()
