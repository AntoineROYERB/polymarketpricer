# Phase 4 — Edge Scoring — API Endpoints

> **Goal**: Expose edge metrics via dedicated endpoints and augment existing leaderboard + wallet endpoints with edge data.
> **AI Agent Instructions**: Create `app/api/v1/leaderboard_edge.py` (or add to existing leaderboard router), update existing endpoint schemas, and register new routes.

---

## New Endpoints

### `GET /api/v1/leaderboard/edge`

Returns wallets ranked by `edge_score` descending. Edge score measures a wallet's ability to predict market outcomes (ROI per trade on resolved markets).

**Query Parameters:**

| Param | Type | Default | Valid Range | Description |
|-------|------|---------|-------------|-------------|
| `limit` | int | 50 | 1–200 | Max results |
| `offset` | int | 0 | ≥ 0 | Pagination offset |

**Response `200 OK`:**

```json
{
  "data": [
    {
      "wallet": "0x1234...abcd",
      "edge_score": 0.95,
      "avg_edge": 0.42,
      "edge_consistency": 0.78,
      "num_edge_trades": 34,
      "rank": 1
    },
    {
      "wallet": "0x5678...ef01",
      "edge_score": 0.88,
      "avg_edge": 0.35,
      "edge_consistency": 0.72,
      "num_edge_trades": 28,
      "rank": 2
    }
  ],
  "limit": 50,
  "offset": 0
}
```

**Error Responses:**

| Status | Body | When |
|--------|------|------|
| 422 | `{"detail": [...]}` | Invalid query params (e.g. `limit=999`) |
| 500 | `{"detail": "Internal server error"}` | Database failure |

---

### `GET /api/v1/wallets/{address}/edge`

Returns detailed edge metrics for a specific wallet.

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `address` | str | Ethereum address (0x-prefixed) |

**Response `200 OK`:**

```json
{
  "wallet": "0x1234...abcd",
  "snapshot_date": "2026-06-26",
  "avg_edge": 0.42,
  "median_edge": 0.35,
  "edge_consistency": 0.78,
  "edge_volatility": 1.23,
  "edge_score": 0.95,
  "num_edge_trades": 34,
  "positive_edge_trades": 27,
  "negative_edge_trades": 7,
  "computed_at": "2026-06-26T12:00:00+00:00"
}
```

**Responses:**

| Status | Body | When |
|--------|------|------|
| 200 | `WalletEdgeSnapshot` | Wallet has edge data |
| 200 | `{"wallet": "...", "detail": "No edge data available"}` | Wallet exists but has no edge data |
| 404 | `{"detail": "Wallet not found"}` | Unknown wallet address |

---

## Modifications to Existing Endpoints

### `GET /api/v1/leaderboard`

Add two fields to each `LeaderboardEntry` in the response:

```json
{
  "wallet": "0x1234...abcd",
  "rank": 1,
  "wallet_score": 85.3,
  "roi": 0.45,
  "consistency": 0.72,
  "experience": 0.65,
  "risk_adj_return": 0.30,
  "volume": 1250000.00,
  "edge_score": 0.95,
  "edge_consistency": 0.78,
  "num_edge_trades": 34
}
```

**New fields:**
- `edge_score` — wallet's edge score (normalised [0, 1]), from `wallet_edge_snapshots`
- `edge_consistency` — fraction of trades with positive edge [0, 1]
- `num_edge_trades` — total number of edge-computable trades

No query parameter changes — the fields are always included (nullable if no edge data exists).

### `GET /api/v1/wallets/{address}`

Add an `edge_metrics` object to the wallet profile response:

```json
{
  "wallet": "0x1234...abcd",
  "wallet_score": 85.3,
  "roi": 0.45,
  "analytics": { ... },
  "categories": [ ... ],
  "edge_metrics": {
    "snapshot_date": "2026-06-26",
    "avg_edge": 0.42,
    "edge_consistency": 0.78,
    "edge_score": 0.95,
    "num_edge_trades": 34
  }
}
```

---

## Router Implementation

### New router file: `app/api/v1/edge.py`

```python
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.db.models import WalletEdgeSnapshot, Wallet
from app.models.schemas import (
    EdgeLeaderboardEntry,
    EdgeLeaderboardResponse,
    WalletEdgeSnapshot as WalletEdgeSnapshotSchema,
)

router = APIRouter()


@router.get("/leaderboard/edge", response_model=EdgeLeaderboardResponse)
async def edge_leaderboard(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> EdgeLeaderboardResponse:
    """Rank wallets by edge_score descending."""
    stmt = (
        select(WalletEdgeSnapshot)
        .where(WalletEdgeSnapshot.edge_score.isnot(None))
        .order_by(WalletEdgeSnapshot.edge_score.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    data = [
        EdgeLeaderboardEntry(
            wallet=r.wallet,
            edge_score=Decimal(str(r.edge_score)),
            avg_edge=Decimal(str(r.avg_edge)),
            edge_consistency=(
                Decimal(str(r.edge_consistency)) if r.edge_consistency else None
            ),
            num_edge_trades=r.num_edge_trades,
            rank=offset + idx + 1,
        )
        for idx, r in enumerate(rows)
    ]

    return EdgeLeaderboardResponse(data=data, limit=limit, offset=offset)


@router.get("/wallets/{address}/edge", response_model=WalletEdgeSnapshotSchema)
async def wallet_edge(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletEdgeSnapshotSchema:
    """Return edge metrics for a specific wallet."""
    # Verify wallet exists
    w = await db.execute(select(Wallet).where(Wallet.wallet == address))
    if w.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Get most recent edge snapshot
    stmt = (
        select(WalletEdgeSnapshot)
        .where(WalletEdgeSnapshot.wallet == address)
        .order_by(WalletEdgeSnapshot.snapshot_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    snapshot = result.scalar_one_or_none()

    if snapshot is None:
        return WalletEdgeSnapshotSchema(
            wallet=address,
            snapshot_date=None,
            avg_edge=Decimal("0"),
            num_edge_trades=0,
        )

    return WalletEdgeSnapshotSchema(
        wallet=snapshot.wallet,
        snapshot_date=snapshot.snapshot_date,
        avg_edge=Decimal(str(snapshot.avg_edge)),
        median_edge=(
            Decimal(str(snapshot.median_edge)) if snapshot.median_edge else None
        ),
        edge_consistency=(
            Decimal(str(snapshot.edge_consistency))
            if snapshot.edge_consistency
            else None
        ),
        edge_volatility=(
            Decimal(str(snapshot.edge_volatility))
            if snapshot.edge_volatility
            else None
        ),
        edge_score=(
            Decimal(str(snapshot.edge_score)) if snapshot.edge_score else None
        ),
        num_edge_trades=snapshot.num_edge_trades,
        positive_edge_trades=snapshot.positive_edge_trades,
        negative_edge_trades=snapshot.negative_edge_trades,
        computed_at=snapshot.computed_at,
    )
```

> **Note**: The router above registers endpoints at `/leaderboard/edge` and `/wallets/{address}/edge`. These paths are relative to the `api_router` prefix (which is typically `/api/v1`). The router itself is not prefixed — it adds routes that are included in the main router with their full paths.

### Alternative: Add to existing routers

If preferred, the logic can be added directly:
- Add `edge_leaderboard` to `app/api/v1/leaderboard.py` as a new route `@router.get("/edge")`
- Add `wallet_edge` to `app/api/v1/wallets.py` as a new route `@router.get("/{address}/edge")`

The choice depends on code organisation preferences.

---

## Schema Updates

Add these schemas to `app/models/schemas.py` (already defined in the database schema plan, but included here for completeness):

### New schemas

```python
class WalletEdgeSnapshot(BaseModel):
    wallet: str
    snapshot_date: Optional[date] = None
    avg_edge: Decimal
    median_edge: Optional[Decimal] = None
    edge_consistency: Optional[Decimal] = None
    edge_volatility: Optional[Decimal] = None
    edge_score: Optional[Decimal] = None
    num_edge_trades: int
    positive_edge_trades: Optional[int] = None
    negative_edge_trades: Optional[int] = None
    computed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EdgeLeaderboardEntry(BaseModel):
    wallet: str
    edge_score: Decimal
    avg_edge: Decimal
    edge_consistency: Optional[Decimal] = None
    num_edge_trades: int
    rank: int


class EdgeLeaderboardResponse(BaseModel):
    data: list[EdgeLeaderboardEntry]
    limit: int
    offset: int
```

### Updated schemas

**`LeaderboardEntry`** — add these optional fields:

```python
class LeaderboardEntry(BaseModel):
    wallet: str
    rank: int
    wallet_score: Decimal
    roi: Decimal
    consistency: Decimal
    experience: Decimal
    risk_adj_return: Decimal
    volume: Decimal
    # Phase 4 additions
    edge_score: Optional[Decimal] = None
    edge_consistency: Optional[Decimal] = None
    num_edge_trades: Optional[int] = None

    model_config = {"from_attributes": True}
```

**`WalletDetail`** — add `edge_metrics` field:

```python
class WalletDetail(BaseModel):
    wallet: str
    wallet_score: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    analytics: Optional[dict] = None
    categories: Optional[list[CategoryAnalyticsData]] = None
    # Phase 4 addition
    edge_metrics: Optional[WalletEdgeSnapshot] = None
```

---

## Router Registration

Edit `app/api/router.py` — add the edge router (if using a separate file):

```python
from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.wallets import router as wallets_router
from app.api.v1.markets import router as markets_router
from app.api.v1.categories import router as categories_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.edge import router as edge_router         # NEW

api_router = APIRouter()

api_router.include_router(leaderboard_router, prefix="/leaderboard", tags=["leaderboard"])
api_router.include_router(wallets_router, prefix="/wallets", tags=["wallets"])
api_router.include_router(markets_router, prefix="/markets", tags=["markets"])
api_router.include_router(categories_router, prefix="", tags=["categories"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
api_router.include_router(edge_router, prefix="", tags=["edge"])           # NEW
```

If adding routes directly to existing routers, no registration change is needed.

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `app/api/v1/edge.py` (or add to existing routers) |
| EDIT | `app/models/schemas.py` — add `WalletEdgeSnapshot`, `EdgeLeaderboardEntry`, `EdgeLeaderboardResponse`; update `LeaderboardEntry` and `WalletDetail` |
| EDIT | `app/api/router.py` — register edge router (if separate file) |
| EDIT | `app/api/v1/leaderboard.py` — add `edge_score`, `edge_consistency` to response (if modifying existing) |
| EDIT | `app/api/v1/wallets.py` — add `edge_metrics` to wallet profile (if modifying existing) |

---

## Verification

```bash
# Test edge leaderboard
curl "http://localhost:8000/api/v1/leaderboard/edge?limit=5"

# Test wallet edge detail
curl "http://localhost:8000/api/v1/wallets/0x1234...abcd/edge"

# Test 404 for unknown wallet
curl "http://localhost:8000/api/v1/wallets/0xdeadbeef/edge"

# Test leaderboard includes edge fields
curl "http://localhost:8000/api/v1/leaderboard?limit=3" | python3 -m json.tool

# Test wallet profile includes edge_metrics
curl "http://localhost:8000/api/v1/wallets/0x1234...abcd" | python3 -m json.tool
```
