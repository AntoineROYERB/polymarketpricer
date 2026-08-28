# Phase 3 — Smart Money Detection — API Endpoints

> **Goal**: Expose alerts via REST and real-time WebSocket.
> **AI Agent Instructions**: Create `app/api/v1/alerts.py`, register in `app/api/router.py`, add WebSocket support.

---

## New REST Endpoints

### `GET /api/v1/alerts`

Returns recent high-signal alerts, newest first.

**Query Parameters:**

| Param | Type | Default | Valid Range | Description |
|---|---|---|---|---|
| `limit` | int | 50 | 1–200 | Max results |
| `offset` | int | 0 | ≥ 0 | Pagination offset |
| `category` | str | — | Optional | Filter by category (case-insensitive) |
| `min_score` | int | — | 0–100 | Minimum wallet score filter |
| `wallet` | str | — | Optional | Filter by wallet address (partial match) |

**Response `200 OK`:**

```json
{
  "data": [
    {
      "id": "a1b2c3d4-...",
      "wallet": "0x1234...abcd",
      "market_id": "123456",
      "market_question": "Will candidate X win the election?",
      "action": "NEW_POSITION",
      "price": 0.42,
      "position_size": 12000.00,
      "wallet_score": 89.5,
      "category": "Politics",
      "detected_at": "2026-06-22T12:00:00+00:00",
      "notified_at": "2026-06-22T12:00:05+00:00"
    }
  ],
  "limit": 50,
  "offset": 0
}
```

**Error Responses:**

| Status | Body | When |
|---|---|---|
| 422 | `{"detail": [...]}` | Invalid query params (e.g. `limit=999`) |
| 500 | `{"detail": "Internal server error"}` | Database failure |

### `GET /api/v1/alerts/{wallet}`

Returns alerts for a specific wallet, newest first.

**Path Parameters:**

| Param | Type | Description |
|---|---|---|
| `wallet` | str | Ethereum address (0x-prefixed) |

**Query Parameters:** Same as list endpoint (`limit`, `offset` only — `wallet` filter is implied by path).

**Responses:**

| Status | Body | When |
|---|---|---|
| 200 | `AlertListResponse` | Wallet exists (may have empty data array) |
| 404 | `{"detail": "Wallet not found"}` | Unknown wallet address |

### `GET /api/v1/alerts/stats`

Aggregated alert statistics — useful for dashboard summaries.

**Response `200 OK`:**

```json
{
  "total_alerts": 156,
  "alerts_today": 12,
  "top_categories": [
    {"category": "Politics", "count": 45},
    {"category": "Crypto", "count": 38},
    {"category": "Sports", "count": 22}
  ],
  "top_wallets": [
    {"wallet": "0x1234...", "alert_count": 8}
  ]
}
```

---

## WebSocket Endpoint

### `WS /api/v1/alerts/ws`

Real-time stream of alerts as they are detected by the background poller.

**Connection:**

```
ws://localhost:8000/api/v1/alerts/ws
wss://your-domain.com/api/v1/alerts/ws
```

**Server → Client Messages:**

1. **Alert event** (when a new alert is detected and delivered):

```json
{
  "type": "alert",
  "payload": {
    "id": "a1b2c3d4-...",
    "wallet": "0x1234...abcd",
    "market_id": "123456",
    "market_question": "Will candidate X win?",
    "action": "NEW_POSITION",
    "price": 0.42,
    "position_size": 12000.00,
    "wallet_score": 89.5,
    "category": "Politics",
    "detected_at": "2026-06-22T12:00:00+00:00"
  }
}
```

2. **Heartbeat (ping)** — every 30 seconds:

```json
{"type": "ping"}
```

**Client → Server Messages:**

```json
{"type": "pong"}
```

**Connection Lifecycle:**

| Event | Server Action |
|---|---|
| Client connects | Accept, add to `ConnectionManager` |
| Every 30s | Send `{"type": "ping"}` |
| Client sends `pong` | Nothing (connection stays alive) |
| No `pong` for 90s (3 missed) | Close connection, remove from manager |
| Client disconnects | Remove from `ConnectionManager` |

---

## Router Implementation

Create `app/api/v1/alerts.py`:

```python
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.db.models import Alert, Wallet
from app.models.schemas import AlertItem, AlertListResponse
from app.services.ws_manager import manager

router = APIRouter()


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    category: Optional[str] = None,
    min_score: Optional[Decimal] = None,
    wallet: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    """List alerts, newest first, with optional filters."""
    stmt = select(Alert).order_by(Alert.detected_at.desc())

    if category:
        stmt = stmt.where(Alert.category.ilike(category))
    if min_score is not None:
        stmt = stmt.where(Alert.wallet_score >= min_score)
    if wallet:
        stmt = stmt.where(Alert.wallet.ilike(f"%{wallet}%"))

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return AlertListResponse(
        data=[_alert_to_item(a) for a in alerts],
        limit=limit,
        offset=offset,
    )


@router.get("/{wallet}", response_model=AlertListResponse)
async def wallet_alerts(
    wallet: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    """List alerts for a specific wallet. Returns 404 if wallet is unknown."""
    # Verify wallet exists
    w = await db.execute(select(Wallet).where(Wallet.wallet == wallet))
    if w.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    stmt = (
        select(Alert)
        .where(Alert.wallet == wallet)
        .order_by(Alert.detected_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return AlertListResponse(
        data=[_alert_to_item(a) for a in alerts],
        limit=limit,
        offset=offset,
    )


@router.websocket("/ws")
async def alert_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time alert streaming."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "pong":
                pass  # heartbeat acknowledged — connection is alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/stats", response_model=dict)
async def alert_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """Aggregated alert statistics."""
    total = await db.execute(select(func.count(Alert.id)))
    today = await db.execute(
        select(func.count(Alert.id)).where(
            Alert.detected_at >= func.current_date()
        )
    )
    return {
        "total_alerts": total.scalar() or 0,
        "alerts_today": today.scalar() or 0,
    }


def _alert_to_item(a: Alert) -> AlertItem:
    """Convert SQLAlchemy Alert model to Pydantic AlertItem."""
    return AlertItem(
        id=str(a.id),
        wallet=a.wallet,
        market_id=a.market_id,
        market_question=a.market_question,
        action=a.action,
        price=Decimal(str(a.price)),
        position_size=Decimal(str(a.position_size)),
        wallet_score=Decimal(str(a.wallet_score)),
        category=a.category,
        detected_at=a.detected_at,
        notified_at=a.notified_at,
    )
```

---

## Router Registration

Edit `app/api/router.py` — add the alerts router:

```python
from fastapi import APIRouter

from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.wallets import router as wallets_router
from app.api.v1.markets import router as markets_router
from app.api.v1.categories import router as categories_router
from app.api.v1.alerts import router as alerts_router

api_router = APIRouter()

api_router.include_router(leaderboard_router, prefix="/leaderboard", tags=["leaderboard"])
api_router.include_router(wallets_router, prefix="/wallets", tags=["wallets"])
api_router.include_router(markets_router, prefix="/markets", tags=["markets"])
api_router.include_router(categories_router, prefix="", tags=["categories"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
```

---

## Files to Create / Modify

| Action | Path |
|---|---|
| CREATE | `app/api/v1/alerts.py` |
| EDIT | `app/api/router.py` — import and register `alerts_router` |
