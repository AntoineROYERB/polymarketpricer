# Phase 3 — Smart Money Detection — Discord Delivery

> **Goal**: Deliver alerts to Discord via webhook in real time as they are detected, and broadcast them to WebSocket clients.
> **AI Agent Instructions**: Create `app/services/alert_service.py` with Discord webhook delivery logic and WebSocket broadcasting. Add a background task to `app/main.py` that polls un-notified alerts every 10 seconds.

---

## Architecture

Delivery is handled entirely within the **FastAPI app process** (not Mage AI). A background asyncio task:

1. Polls `alerts WHERE notified_at IS NULL AND delivery_attempts < 3` every 10 seconds
2. For each un-notified alert:
   a. Broadcasts the alert to all connected WebSocket clients
   b. Sends a formatted Discord embed via webhook
   c. On success: sets `notified_at = NOW()`
   d. On failure: increments `delivery_attempts` (max 3 retries)
3. Runs for the lifetime of the app process via FastAPI `lifespan`

```
┌───────────────────────────────────────────────────┐
│                   FastAPI Process                  │
│                                                    │
│  ┌──────────────────┐     ┌────────────────────┐  │
│  │ WebSocket         │◄────│ alert_delivery_loop │  │
│  │ connections       │     │ (async task, 10s)  │  │
│  │ (ConnectionManager)│    │                    │  │
│  └──────────────────┘     │ 1. Poll alerts      │  │
│                           │ 2. WS broadcast      │  │
│  ┌──────────────────┐     │ 3. Discord webhook   │  │
│  │ Discord Webhook  │◄────│ 4. Mark notified     │  │
│  │ (httpx POST)     │     └────────┬────────────┘  │
│  └──────────────────┘              │               │
│                          ┌─────────▼──────────┐   │
│                          │     PostgreSQL      │   │
│                          │    (alerts table)   │   │
│                          └────────────────────┘   │
└───────────────────────────────────────────────────┘
```

---

## Environment Variables

Add to `docker-compose.yml` under the `app` service:

```yaml
environment:
  # ... existing vars ...
  DISCORD_WEBHOOK_URL: "${DISCORD_WEBHOOK_URL}"
  ALERT_POLL_INTERVAL_SECONDS: "10"
```

Add to `.env`:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_id/your_webhook_token
```

### Update `app/config.py`

```python
class Settings(BaseSettings):
    # ... existing fields ...
    discord_webhook_url: str = ""
    alert_poll_interval_seconds: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

---

## Service: `app/services/alert_service.py`

Three core async functions and one pure function for classification.

### Imports and constants

```python
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.db.models import Alert, AlertRule

DISCORD_EMBED_COLORS = {
    "NEW_POSITION": 0x2ECC71,       # Green
    "POSITION_INCREASE": 0x3498DB,  # Blue
    "POSITION_DECREASE": 0xE67E22,  # Orange
    "FULL_EXIT": 0xE74C3C,          # Red
}
```

### 1. `poll_unnotified_alerts`

```python
async def poll_unnotified_alerts(db: AsyncSession) -> list[Alert]:
    """Fetch undelivered alerts (oldest first, max 20, max 3 retries)."""
    stmt = (
        select(Alert)
        .where(Alert.notified_at.is_(None))
        .where(Alert.delivery_attempts < 3)
        .order_by(Alert.detected_at.asc())
        .limit(20)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

### 2. `classify_action` (pure function, also used in transformer)

```python
def classify_action(shares_before: Optional[float], shares_after: Optional[float]) -> Optional[str]:
    """Classify a position change into an alert action type.

    Returns None if there is no meaningful change.
    """
    before = float(shares_before or 0)
    after = float(shares_after or 0)

    if before == 0 and after > 0:
        return "NEW_POSITION"
    elif after > before:
        return "POSITION_INCREASE"
    elif after < before and after > 0:
        return "POSITION_DECREASE"
    elif after == 0 and before > 0:
        return "FULL_EXIT"
    return None
```

### 3. `send_discord_alert`

```python
def _format_action(action: str, price: float) -> str:
    """Convert action enum to human-readable Discord field value."""
    labels = {
        "NEW_POSITION": f"BUY (New Position @ ${price:.4f})",
        "POSITION_INCREASE": f"BUY (Increase @ ${price:.4f})",
        "POSITION_DECREASE": f"SELL (Decrease @ ${price:.4f})",
        "FULL_EXIT": f"SELL (Full Exit @ ${price:.4f})",
    }
    return labels.get(action, action)


async def send_discord_alert(alert: Alert, webhook_url: str) -> bool:
    """Send a formatted Discord embed for the given alert. Returns True on success."""
    color = DISCORD_EMBED_COLORS.get(alert.action, 0x95A5A6)

    embed = {
        "embeds": [{
            "title": "🚨 Smart Money Alert",
            "color": color,
            "fields": [
                {
                    "name": "Trader",
                    "value": f"`{alert.wallet[:10]}...{alert.wallet[-4:]}`",
                    "inline": True,
                },
                {
                    "name": "Score",
                    "value": str(alert.wallet_score),
                    "inline": True,
                },
                {
                    "name": "Category",
                    "value": alert.category,
                    "inline": True,
                },
                {
                    "name": "Action",
                    "value": _format_action(alert.action, float(alert.price)),
                    "inline": True,
                },
                {
                    "name": "Market",
                    "value": alert.market_question,
                    "inline": False,
                },
                {
                    "name": "Price",
                    "value": f"${float(alert.price):.4f}",
                    "inline": True,
                },
                {
                    "name": "Position Size",
                    "value": f"${float(alert.position_size):,.2f}",
                    "inline": True,
                },
            ],
            "footer": {"text": "Polymarket Smart Money Tracker"},
            "timestamp": alert.detected_at.isoformat(),
        }]
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(webhook_url, json=embed)
            return resp.status_code in (200, 204)
        except httpx.RequestError:
            return False
```

### 4. `mark_notified`

```python
async def mark_notified(alert_id: str, success: bool, db: AsyncSession) -> None:
    """Mark alert as notified or increment retry counter."""
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if alert is None:
        return
    if success:
        alert.notified_at = datetime.now(timezone.utc)
    else:
        alert.delivery_attempts = (alert.delivery_attempts or 0) + 1
    await db.commit()
```

---

## WebSocket Manager: `app/services/ws_manager.py`

Manages active WebSocket connections, broadcasts alerts, and sends heartbeats.

```python
from fastapi import WebSocket
from app.db.models import Alert


class ConnectionManager:
    """Manages active WebSocket connections for real-time alert streaming."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_alert(self, alert: Alert) -> None:
        """Send alert payload to all connected clients. Removes dead connections."""
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
        """Send a ping to all connected clients. Removes dead connections."""
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json({"type": "ping"})
            except Exception:
                dead.append(conn)
        for c in dead:
            self.disconnect(c)


# Singleton instance — import this in api/v1/alerts.py and main.py
manager = ConnectionManager()
```

---

## Background Delivery Loop: Update `app/main.py`

Replace the existing `app` instantiation block (lines 1–12) with this version that uses `lifespan`:

```python
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.config import settings
from app.db.engine import AsyncSessionLocal
from app.services.alert_service import (
    poll_unnotified_alerts,
    send_discord_alert,
    mark_notified,
)
from app.services.ws_manager import manager


async def alert_delivery_loop() -> None:
    """Background task: poll un-notified alerts → broadcast via WS → deliver to Discord."""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                alerts = await poll_unnotified_alerts(db)
                for alert in alerts:
                    # 1. Broadcast via WebSocket (always, even if Discord fails)
                    await manager.broadcast_alert(alert)

                    # 2. Send to Discord webhook
                    if settings.discord_webhook_url:
                        success = await send_discord_alert(
                            alert, settings.discord_webhook_url
                        )
                    else:
                        success = True  # WS-only mode (no Discord configured)

                    # 3. Mark as notified (or increment retry counter)
                    await mark_notified(str(alert.id), success, db)

                    # Small delay between alerts to avoid Discord rate limits
                    await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Alert delivery error: {e}")

        await asyncio.sleep(settings.alert_poll_interval_seconds)


async def _heartbeat_loop() -> None:
    """Send WebSocket ping every 30 seconds to keep connections alive."""
    while True:
        await asyncio.sleep(30)
        await manager.send_heartbeat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup, cancel on shutdown."""
    delivery_task = asyncio.create_task(alert_delivery_loop())
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    yield
    delivery_task.cancel()
    heartbeat_task.cancel()


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

**Note**: This replaces the entire `app/main.py` content.

---

## Retry Logic

| delivery_attempts | Action |
|---|---|
| 0 (initial) | Attempt webhook delivery immediately |
| 1 | Retry on next poll cycle (~10s later) |
| 2 | Retry on next poll cycle |
| 3 | Abandoned — alert stays but never retried |

---

## Files to Create / Modify

| Action | Path |
|---|---|
| CREATE | `app/services/alert_service.py` |
| CREATE | `app/services/ws_manager.py` |
| EDIT | `app/config.py` — add `discord_webhook_url`, `alert_poll_interval_seconds` |
| EDIT | `app/main.py` — replace everything with lifespan-based version |
| EDIT | `docker-compose.yml` — add `DISCORD_WEBHOOK_URL` and `ALERT_POLL_INTERVAL_SECONDS` env vars to `app` service |
| EDIT | `.env` — add `DISCORD_WEBHOOK_URL` |
