from fastapi import WebSocket

from app.db.models import Alert


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_alert(self, alert: Alert) -> None:
        payload = {
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
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                dead_connections.append(connection)
        for conn in dead_connections:
            self.disconnect(conn)

    async def send_heartbeat(self) -> None:
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json({"type": "ping"})
            except Exception:
                dead.append(conn)
        for c in dead:
            self.disconnect(c)


manager = ConnectionManager()
