# Phase 2 — API Endpoints: Category Analytics

> **Specification** for implementing 4 new API endpoints, Pydantic schemas, service layer, and router updates.
> **Status**: Draft — ready for implementation.
> **Depends on**: Phase 2 DB schema (migration `002`, `CategoryAnalytic` + `CategoryRanking` models in `app/db/models.py`)

---

## Table of Contents

1. [Overview](#1-overview)
2. [New Pydantic Schemas](#2-new-pydantic-schemas)
3. [Service Layer](#3-service-layer)
4. [Router](#4-router)
5. [Router Registration](#5-router-registration)
6. [WalletProfile Update](#6-walletprofile-update)
7. [Category Validation Utility](#7-category-validation-utility)
8. [Error Handling](#8-error-handling)
9. [Test Plan](#9-test-plan)
10. [Implementation Order](#10-implementation-order)

---

## 1. Overview

Phase 2 adds 4 endpoints that expose per-category wallet analytics and category-specific leaderboards. The endpoints query two new tables that are created by the Phase 2 database migration:

| Table | Contents |
|---|---|
| `category_analytics` | Per-wallet, per-category, per-day analytical snapshot (PK: `wallet`, `category`, `snapshot_date`) |
| `category_rankings` | Materialized leaderboard lists per category (PK: `wallet`, `category`, `snapshot_date`, `list_type`) |

These tables are populated by the Phase 2 ETL pipeline (`category_analytics`) and are assumed to exist when these endpoints are called.

### Endpoint Summary

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/leaderboard/{category}` | Top traders in a category |
| `GET` | `/api/v1/leaderboard/{category}/specialists` | Category specialists only |
| `GET` | `/api/v1/wallets/{address}/categories` | Per-category breakdown for a wallet |
| `GET` | `/api/v1/wallets/{address}/categories/{category}` | Single category detail for a wallet |

---

## 2. New Pydantic Schemas

All new models go in **`app/models/schemas.py`**. Each must have `model_config = {"from_attributes": True}` to support ORM-to-Pydantic conversion.

### 2.1 `CategoryLeaderboardEntry`

```python
class CategoryLeaderboardEntry(BaseModel):
    rank: int
    wallet: str
    wallet_score: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    total_pnl: Optional[Decimal] = None
    num_trades: int = 0
    total_volume: Optional[Decimal] = None
    is_specialist: bool = False

    model_config = {"from_attributes": True}
```

Maps to a row in `category_rankings`. The `is_specialist` field indicates whether this entry appears in both the `top_50` and `specialists` list types (or is derived from the `category_analytics.is_specialist` column if the ranking table does not contain it — see implementation note).

> **Implementation note**: `category_rankings` does not have an `is_specialist` column. The `is_specialist` value should be derived by checking whether the wallet also exists in the `specialists` list type for this category, or by joining with `category_analytics`. For simplicity in the first implementation, set `is_specialist` to `True` when the route is `/specialists` (since all returned entries are specialists by definition). For the main leaderboard, set it based on whether the wallet has `is_specialist = True` in `category_analytics`.

### 2.2 `CategoryLeaderboardResponse`

```python
class CategoryLeaderboardResponse(BaseModel):
    category: str
    data: list[CategoryLeaderboardEntry]
    limit: int
    offset: int
```

Wrapper for paginated category leaderboard responses.

### 2.3 `WalletCategorySummary`

```python
class WalletCategorySummary(BaseModel):
    category: str
    num_trades: int = 0
    total_volume: Optional[Decimal] = None
    total_pnl: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    profit_factor: Optional[Decimal] = None
    avg_position_size: Optional[Decimal] = None
    is_specialist: bool = False
    category_rank: Optional[int] = None

    model_config = {"from_attributes": True}
```

Maps to a row in `category_analytics`. Returned in the wallet categories list.

### 2.4 `WalletCategoryResponse`

```python
class WalletCategoryResponse(BaseModel):
    wallet: str
    categories: list[WalletCategorySummary]
```

### 2.5 `CategoryDetailResponse`

```python
class CategoryDetailResponse(BaseModel):
    wallet: str
    category: str
    num_trades: int = 0
    total_volume: Optional[Decimal] = None
    total_cost_basis: Optional[Decimal] = None
    total_pnl: Optional[Decimal] = None
    total_realized_pnl: Optional[Decimal] = None
    total_unrealized_pnl: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    num_resolved_positions: int = 0
    profit_factor: Optional[Decimal] = None
    avg_position_size: Optional[Decimal] = None
    avg_holding_duration: Optional[str] = None
    is_specialist: bool = False
    category_rank: Optional[int] = None

    model_config = {"from_attributes": True}
```

Full detail for a single wallet+category combination. The `avg_holding_duration` field is stored as `Interval` in the DB and must be converted to `str` during serialization (matching the pattern used in `WalletAnalyticsData`).

### 2.6 Placement in File

Insert all new classes **before** `MarketSummary` (to keep related wallet/leaderboard types grouped). The order in the file should be:

```
LeaderboardEntry         (existing)
LeaderboardResponse      (existing)
PositionSummary          (existing)
WalletAnalyticsData      (existing)
WalletProfile            (existing — will be modified)
CategoryLeaderboardEntry  (NEW)
CategoryLeaderboardResponse (NEW)
WalletCategorySummary     (NEW)
WalletCategoryResponse    (NEW)
CategoryDetailResponse    (NEW)
MarketSummary             (existing)
MarketListResponse        (existing)
```

---

## 3. Service Layer

Create a new file **`app/services/category_service.py`** with 4 async functions.

### 3.1 Full Code

```python
"""
Service functions for category analytics endpoints.
"""
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CategoryAnalytic, CategoryRanking, Wallet


async def get_category_leaderboard(
    db: AsyncSession,
    category: str,
    limit: int = 50,
    offset: int = 0,
) -> list[CategoryRanking]:
    """Return the top traders in a specific category.

    Queries ``category_rankings`` with ``list_type='top_50'`` ordered by rank.

    Args:
        db: Database session.
        category: Category string (must match DB format, e.g. 'Politics').
        limit: Maximum number of rows to return.
        offset: Number of rows to skip.

    Returns:
        List of ``CategoryRanking`` ORM objects.
    """
    stmt = (
        select(CategoryRanking)
        .where(
            CategoryRanking.category == category,
            CategoryRanking.list_type == "top_50",
        )
        .order_by(CategoryRanking.rank)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_category_specialists(
    db: AsyncSession,
    category: str,
    limit: int = 50,
) -> list[CategoryRanking]:
    """Return specialist traders in a specific category.

    Queries ``category_rankings`` with ``list_type='specialists'`` ordered by rank.

    Args:
        db: Database session.
        category: Category string.
        limit: Maximum number of rows to return.

    Returns:
        List of ``CategoryRanking`` ORM objects.
    """
    stmt = (
        select(CategoryRanking)
        .where(
            CategoryRanking.category == category,
            CategoryRanking.list_type == "specialists",
        )
        .order_by(CategoryRanking.rank)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_wallet_categories(
    db: AsyncSession,
    address: str,
) -> list[CategoryAnalytic]:
    """Return all category analytics for a given wallet.

    Queries ``category_analytics`` for the most recent snapshot of each category.

    Args:
        db: Database session.
        address: Wallet address.

    Returns:
        List of ``CategoryAnalytic`` ORM objects (one per category that the wallet has
        traded in). Empty list if the wallet has no category data.
    """
    # Subquery to get the latest snapshot_date per category for this wallet
    latest_per_category = (
        select(
            CategoryAnalytic.category,
            CategoryAnalytic.snapshot_date,
        )
        .where(CategoryAnalytic.wallet == address)
        .order_by(
            CategoryAnalytic.category,
            CategoryAnalytic.snapshot_date.desc(),
        )
        .distinct(CategoryAnalytic.category)
        .subquery()
    )

    stmt = (
        select(CategoryAnalytic)
        .join(
            latest_per_category,
            (CategoryAnalytic.category == latest_per_category.c.category)
            & (CategoryAnalytic.snapshot_date == latest_per_category.c.snapshot_date),
        )
        .where(CategoryAnalytic.wallet == address)
        .order_by(CategoryAnalytic.category)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_wallet_category_detail(
    db: AsyncSession,
    address: str,
    category: str,
) -> Optional[CategoryAnalytic]:
    """Return the category detail for a specific wallet+category combination.

    Queries ``category_analytics`` for the most recent snapshot of this wallet
    in the given category.

    Args:
        db: Database session.
        address: Wallet address.
        category: Category string.

    Returns:
        A single ``CategoryAnalytic`` or ``None`` if not found.
    """
    stmt = (
        select(CategoryAnalytic)
        .where(
            CategoryAnalytic.wallet == address,
            CategoryAnalytic.category == category,
        )
        .order_by(CategoryAnalytic.snapshot_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def wallet_exists(
    db: AsyncSession,
    address: str,
) -> bool:
    """Check if a wallet address exists in the database.

    Args:
        db: Database session.
        address: Wallet address to check.

    Returns:
        ``True`` if the wallet exists, ``False`` otherwise.
    """
    stmt = select(Wallet.wallet).where(Wallet.wallet == address)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Helper: convert ORM objects to Pydantic schemas
# ---------------------------------------------------------------------------

def _to_decimal(val: Any) -> Optional[Decimal]:
    """Safely convert a value to Decimal, returning None for None inputs."""
    if val is None:
        return None
    return Decimal(str(val))


def ranking_to_leaderboard_entry(
    row: CategoryRanking,
    is_specialist: bool = False,
) -> dict[str, Any]:
    """Convert a CategoryRanking ORM row to a dict suitable for CategoryLeaderboardEntry.

    Args:
        row: ORM object from category_rankings table.
        is_specialist: Whether this wallet is a specialist in this category.

    Returns:
        Dict matching CategoryLeaderboardEntry fields.
    """
    return {
        "rank": row.rank,
        "wallet": row.wallet,
        "wallet_score": _to_decimal(row.wallet_score),
        "roi": _to_decimal(row.roi),
        "win_rate": _to_decimal(row.win_rate),
        "total_pnl": _to_decimal(row.total_pnl),
        "num_trades": row.num_trades or 0,
        "total_volume": _to_decimal(row.total_volume),
        "is_specialist": is_specialist,
    }


def analytic_to_category_summary(
    row: CategoryAnalytic,
) -> dict[str, Any]:
    """Convert a CategoryAnalytic ORM row to a dict suitable for WalletCategorySummary.

    Args:
        row: ORM object from category_analytics table.

    Returns:
        Dict matching WalletCategorySummary fields.
    """
    return {
        "category": row.category,
        "num_trades": row.num_trades or 0,
        "total_volume": _to_decimal(row.total_volume),
        "total_pnl": _to_decimal(row.total_pnl),
        "roi": _to_decimal(row.roi),
        "win_rate": _to_decimal(row.win_rate),
        "profit_factor": _to_decimal(row.profit_factor),
        "avg_position_size": _to_decimal(row.avg_position_size),
        "is_specialist": row.is_specialist if hasattr(row, "is_specialist") else False,
        "category_rank": row.category_rank if hasattr(row, "category_rank") else None,
    }


def analytic_to_category_detail(
    row: CategoryAnalytic,
) -> dict[str, Any]:
    """Convert a CategoryAnalytic ORM row to a dict suitable for CategoryDetailResponse.

    Handles conversion of ``avg_holding_duration`` from ``Interval`` to ``str``.

    Args:
        row: ORM object from category_analytics table.

    Returns:
        Dict matching CategoryDetailResponse fields.
    """
    avg_duration = row.avg_holding_duration
    avg_duration_str = str(avg_duration) if avg_duration is not None else None

    return {
        "wallet": row.wallet,
        "category": row.category,
        "num_trades": row.num_trades or 0,
        "total_volume": _to_decimal(row.total_volume),
        "total_cost_basis": _to_decimal(row.total_cost_basis),
        "total_pnl": _to_decimal(row.total_pnl),
        "total_realized_pnl": _to_decimal(row.total_realized_pnl),
        "total_unrealized_pnl": _to_decimal(row.total_unrealized_pnl),
        "roi": _to_decimal(row.roi),
        "win_rate": _to_decimal(row.win_rate),
        "num_resolved_positions": row.num_resolved_positions or 0,
        "profit_factor": _to_decimal(row.profit_factor),
        "avg_position_size": _to_decimal(row.avg_position_size),
        "avg_holding_duration": avg_duration_str,
        "is_specialist": row.is_specialist if hasattr(row, "is_specialist") else False,
        "category_rank": row.category_rank if hasattr(row, "category_rank") else None,
    }
```

### 3.2 Design Decisions

1. **Latest snapshot per category**: Wallet category endpoints always return the most recent snapshot date's data. This is implemented via a `DISTINCT ON` subquery pattern.

2. **Helper functions**: The `_to_decimal()`, `ranking_to_leaderboard_entry()`, `analytic_to_category_summary()`, and `analytic_to_category_detail()` helpers are provided but marked as optional — the router may choose to use `model_validate()` with `from_attributes=True` instead. The helpers exist for cases where additional transformations (like `Interval → str`) are needed.

3. **`wallet_exists`**: A separate function exists so the router can check wallet existence independently of fetching category data (reduces DB load when the wallet doesn't exist).

---

## 4. Router

Create a new file **`app/api/v1/categories.py`** with 4 endpoint handlers.

### 4.1 Full Code

```python
"""
API endpoints for category analytics.

Includes:
- Category leaderboard (top traders per category)
- Category specialists
- Wallet category breakdown
- Wallet category detail
"""
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.enums import MarketCategory
from app.models.schemas import (
    CategoryDetailResponse,
    CategoryLeaderboardEntry,
    CategoryLeaderboardResponse,
    WalletCategoryResponse,
    WalletCategorySummary,
)
from app.services.category_service import (
    analytic_to_category_detail,
    analytic_to_category_summary,
    get_category_leaderboard as get_category_leaderboard_data,
    get_category_specialists as get_category_specialists_data,
    get_wallet_categories as get_wallet_categories_data,
    get_wallet_category_detail as get_wallet_category_detail_data,
    ranking_to_leaderboard_entry,
    wallet_exists,
)
from app.utils.category import normalize_category, validate_category

router = APIRouter()


@router.get(
    "/leaderboard/{category}",
    response_model=CategoryLeaderboardResponse,
    summary="Category Leaderboard",
    description="Top traders in a specific category, ranked by wallet_score.",
)
async def category_leaderboard(
    category: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CategoryLeaderboardResponse:
    """Return paginated leaderboard for a single category."""
    # Validate and normalize category
    norm_category = validate_category(category)
    if norm_category is None:
        valid = sorted(m.value for m in MarketCategory)
        raise HTTPException(
            status_code=404,
            detail=f"Invalid category '{category}'. Valid categories: {', '.join(valid)}",
        )

    entries = await get_category_leaderboard_data(db, norm_category, limit, offset)

    return CategoryLeaderboardResponse(
        category=category.lower(),
        data=[_build_leaderboard_entry(e) for e in entries],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/leaderboard/{category}/specialists",
    response_model=CategoryLeaderboardResponse,
    summary="Category Specialists",
    description="Specialist traders in a specific category.",
)
async def category_specialists(
    category: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> CategoryLeaderboardResponse:
    """Return specialist traders for a single category."""
    # Validate and normalize category
    norm_category = validate_category(category)
    if norm_category is None:
        valid = sorted(m.value for m in MarketCategory)
        raise HTTPException(
            status_code=404,
            detail=f"Invalid category '{category}'. Valid categories: {', '.join(valid)}",
        )

    entries = await get_category_specialists_data(db, norm_category, limit)

    return CategoryLeaderboardResponse(
        category=category.lower(),
        data=[_build_leaderboard_entry(e, is_specialist=True) for e in entries],
        limit=limit,
        offset=0,
    )


@router.get(
    "/wallets/{address}/categories",
    response_model=WalletCategoryResponse,
    summary="Wallet Categories",
    description="Per-category performance breakdown for a specific wallet.",
)
async def wallet_categories(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletCategoryResponse:
    """Return all category analytics for a wallet."""
    # Check wallet exists
    if not await wallet_exists(db, address):
        raise HTTPException(status_code=404, detail="Wallet not found")

    rows = await get_wallet_categories_data(db, address)

    return WalletCategoryResponse(
        wallet=address,
        categories=[WalletCategorySummary(**analytic_to_category_summary(r)) for r in rows],
    )


@router.get(
    "/wallets/{address}/categories/{category}",
    response_model=CategoryDetailResponse,
    summary="Wallet Category Detail",
    description="Detailed analytics for a specific wallet+category combination.",
)
async def wallet_category_detail(
    address: str,
    category: str,
    db: AsyncSession = Depends(get_db),
) -> CategoryDetailResponse:
    """Return detailed analytics for a wallet in a specific category."""
    # Validate and normalize category
    norm_category = validate_category(category)
    if norm_category is None:
        valid = sorted(m.value for m in MarketCategory)
        raise HTTPException(
            status_code=404,
            detail=f"Invalid category '{category}'. Valid categories: {', '.join(valid)}",
        )

    # Check wallet exists
    if not await wallet_exists(db, address):
        raise HTTPException(status_code=404, detail="Wallet not found")

    row = await get_wallet_category_detail_data(db, address, norm_category)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for wallet '{address}' in category '{category}'",
        )

    return CategoryDetailResponse(**analytic_to_category_detail(row))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_leaderboard_entry(
    row: Any,
    is_specialist: bool = False,
) -> CategoryLeaderboardEntry:
    """Build a ``CategoryLeaderboardEntry`` from a ``CategoryRanking`` ORM row.

    Handles ``None``-to-``Decimal(0)`` conversion for numeric fields to match
    the pattern established in ``app/api/v1/leaderboard.py:_to_entry``.
    """
    def _d(val: Any) -> Decimal:
        if val is None:
            return Decimal(0)
        return Decimal(str(val))

    return CategoryLeaderboardEntry(
        rank=row.rank,
        wallet=row.wallet,
        wallet_score=_d(getattr(row, "wallet_score", None)),
        roi=_d(getattr(row, "roi", None)),
        win_rate=_d(getattr(row, "win_rate", None)),
        total_pnl=_d(getattr(row, "total_pnl", None)),
        num_trades=row.num_trades or 0,
        total_volume=_d(getattr(row, "total_volume", None)),
        is_specialist=is_specialist,
    )
```

### 4.2 Endpoint Specifications

#### `GET /api/v1/leaderboard/{category}`

| Aspect | Detail |
|---|---|
| **Path param** | `category` — case-insensitive, one of: `politics`, `crypto`, `sports`, `economics`, `technology`, `ai`, `geopolitics`, `entertainment` |
| **Query params** | `limit` (int, default 50, min 1, max 200), `offset` (int, default 0, min 0) |
| **Success** | `200` — `CategoryLeaderboardResponse` with `data` array |
| **Error** | `404` — Invalid category (not in `MarketCategory`) |

**JSON response shape**:
```json
{
  "category": "politics",
  "data": [
    {
      "rank": 1,
      "wallet": "0x17e5...",
      "wallet_score": 0.85,
      "roi": 41.29,
      "win_rate": 0.62,
      "total_pnl": 37053.07,
      "num_trades": 840,
      "total_volume": 89730.34,
      "is_specialist": true
    }
  ],
  "limit": 50,
  "offset": 0
}
```

#### `GET /api/v1/leaderboard/{category}/specialists`

| Aspect | Detail |
|---|---|
| **Path param** | `category` — same as above |
| **Query params** | `limit` (int, default 50, min 1, max 200) — no `offset` |
| **Success** | `200` — same `CategoryLeaderboardResponse` shape, but `is_specialist` is always `true` for all entries |
| **Error** | `404` — Invalid category |

All entries have `"is_specialist": true` by definition since they come from the `specialists` list type.

#### `GET /api/v1/wallets/{address}/categories`

| Aspect | Detail |
|---|---|
| **Path param** | `address` — wallet address (e.g. `0x...`) |
| **Query params** | None |
| **Success** | `200` — `WalletCategoryResponse` |
| **Error** | `404` — Wallet address not found in `wallets` table |

**JSON response shape**:
```json
{
  "wallet": "0x17e5...",
  "categories": [
    {
      "category": "politics",
      "num_trades": 840,
      "total_volume": 89730.34,
      "total_pnl": 37053.07,
      "roi": 41.29,
      "win_rate": 0.62,
      "profit_factor": 3.21,
      "avg_position_size": 106.82,
      "is_specialist": true,
      "category_rank": 1
    }
  ]
}
```

#### `GET /api/v1/wallets/{address}/categories/{category}`

| Aspect | Detail |
|---|---|
| **Path param** | `address`, `category` |
| **Query params** | None |
| **Success** | `200` — `CategoryDetailResponse` |
| **Error** | `404` — Wallet not found, invalid category, or no data for wallet+category |

**JSON response shape**:
```json
{
  "wallet": "0x17e5...",
  "category": "politics",
  "num_trades": 840,
  "total_volume": 89730.34,
  "total_cost_basis": 52300.00,
  "total_pnl": 37053.07,
  "total_realized_pnl": 28000.00,
  "total_unrealized_pnl": 9053.07,
  "roi": 41.29,
  "win_rate": 0.62,
  "num_resolved_positions": 120,
  "profit_factor": 3.21,
  "avg_position_size": 106.82,
  "avg_holding_duration": "7 days, 3:42:00",
  "is_specialist": true,
  "category_rank": 1
}
```

---

## 5. Router Registration

Update **`app/api/router.py`** to include the new `categories` router.

### 5.1 Modified File

```python
from fastapi import APIRouter

from app.api.v1.leaderboard import router as leaderboard_router
from app.api.v1.wallets import router as wallets_router
from app.api.v1.markets import router as markets_router
from app.api.v1.categories import router as categories_router    # NEW

api_router = APIRouter()

api_router.include_router(leaderboard_router, prefix="/leaderboard", tags=["leaderboard"])
api_router.include_router(wallets_router, prefix="/wallets", tags=["wallets"])
api_router.include_router(markets_router, prefix="/markets", tags=["markets"])
api_router.include_router(categories_router, prefix="", tags=["categories"])  # NEW
```

### 5.2 Why `prefix=""`

The categories router defines routes with the full path prefix built in:

| Route definition | Resulting path |
|---|---|
| `GET /leaderboard/{category}` | `/api/v1/leaderboard/{category}` |
| `GET /leaderboard/{category}/specialists` | `/api/v1/leaderboard/{category}/specialists` |
| `GET /wallets/{address}/categories` | `/api/v1/wallets/{address}/categories` |
| `GET /wallets/{address}/categories/{category}` | `/api/v1/wallets/{address}/categories/{category}` |

Since `api_router` is mounted at `/api/v1` in `main.py`, using `prefix=""` produces the correct final paths.

### 5.3 Route Precedence

The categories router is registered **after** the leaderboard and wallets routers. This ensures that literal path matches (e.g. `/leaderboard/emerging` on the leaderboard router) are resolved before parameterised matches (`/leaderboard/{category}` on the categories router). FastAPI prioritises the first registered matching route for a given path, so literal paths from the earlier routers take precedence.

---

## 6. WalletProfile Update

### 6.1 Schema Update (`app/models/schemas.py`)

Add a `categories` field to the existing `WalletProfile` class:

```python
class WalletProfile(BaseModel):
    wallet: str
    main_wallet: Optional[str] = None
    label: Optional[str] = None
    is_tracked: bool = True
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    last_position_sync: Optional[datetime] = None
    last_trade_sync: Optional[datetime] = None
    analytics: Optional[WalletAnalyticsData] = None
    current_positions: list[PositionSummary] = []
    rank: Optional[int] = None
    categories: list[WalletCategorySummary] = []  # NEW — default empty list

    model_config = {"from_attributes": True}
```

### 6.2 Service Update (`app/services/wallet_service.py`)

Update the `get_wallet_profile` flow (called by the router in `wallets.py`) to also fetch category data. The update is in the **router** (`wallets.py`), not the service, since the service returns the ORM object and composition happens in the router.

**Modified `app/api/v1/wallets.py`**:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.schemas import WalletAnalyticsData, WalletProfile, WalletCategorySummary
from app.services.wallet_service import (
    get_wallet_analytics,
    get_wallet_positions,
    get_wallet_profile,
)
from app.services.category_service import (          # NEW
    get_wallet_categories as get_wallet_categories_data,
    analytic_to_category_summary,
)

router = APIRouter()


@router.get("/{address}", response_model=WalletProfile)
async def wallet_profile(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletProfile:
    wallet = await get_wallet_profile(db, address)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    analytics = await get_wallet_analytics(db, address)
    positions = await get_wallet_positions(db, address)
    categories = await get_wallet_categories_data(db, address)  # NEW

    profile = WalletProfile.model_validate(wallet)

    if analytics is not None:
        analytics_data = WalletAnalyticsData.model_validate(analytics)
        if analytics.avg_holding_duration is not None:
            analytics_data.avg_holding_duration = str(analytics.avg_holding_duration)
        profile.analytics = analytics_data

    profile.current_positions = positions
    profile.categories = [                               # NEW
        WalletCategorySummary(**analytic_to_category_summary(r)) for r in categories
    ]

    return profile
```

### 6.3 Performance Note

The `categories` field triggers an additional query (`get_wallet_categories_data`) on every wallet profile request. If this becomes a performance concern, the categories data could be:
- Lazy-loaded (optional query param `include_categories=false`)
- Cached
- Pre-joined in the service

For the initial implementation, eager loading is acceptable since the category query is scoped to a single wallet and is fast.

---

## 7. Category Validation Utility

Create a new utility module **`app/utils/category.py`**.

### 7.1 Full Code

```python
"""
Category validation and normalisation utilities.
"""
from typing import Optional

from app.models.enums import MarketCategory


# Build a mapping: lowercase value -> canonical (enum) value
_CATEGORY_MAP: dict[str, str] = {
    member.value.lower(): member.value
    for member in MarketCategory
}


def validate_category(category: str) -> Optional[str]:
    """Validate and normalise a category string.

    Performs a case-insensitive lookup against the ``MarketCategory`` enum.
    Accepts inputs like ``"politics"``, ``"Politics"``, ``"POLITICS"`` and
    returns the canonical form (``"Politics"``) used in the database.

    Args:
        category: Raw category string from the path parameter.

    Returns:
        The canonical category string if valid, or ``None`` if the category
        is not recognised.
    """
    return _CATEGORY_MAP.get(category.lower())


def normalize_category(category: str) -> Optional[str]:
    """Alias for ``validate_category``.

    Provided for readability when the intent is specifically to normalise
    rather than validate.
    """
    return validate_category(category)


def get_valid_categories() -> list[str]:
    """Return a sorted list of all valid category strings (lowercase)."""
    return sorted(_CATEGORY_MAP.keys())
```

### 7.2 Usage

```python
from app.utils.category import validate_category, get_valid_categories

norm = validate_category("Politics")   # Returns "Politics"
norm = validate_category("politics")   # Returns "Politics"
norm = validate_category("invalid")    # Returns None
```

### 7.3 Testing

```python
def test_validate_category():
    from app.utils.category import validate_category

    assert validate_category("politics") == "Politics"
    assert validate_category("CRYPTO") == "Crypto"
    assert validate_category("sports") == "Sports"
    assert validate_category("invalid") is None
    assert validate_category("") is None
```

---

## 8. Error Handling

### 8.1 Error Matrix

| Scenario | HTTP Status | `detail` Pattern |
|---|---|---|
| Invalid category path parameter | `404` | `Invalid category '{value}'. Valid categories: Politics, Crypto, ...` |
| Unknown wallet address | `404` | `Wallet not found` |
| Wallet exists but no category data (detail endpoint) | `404` | `No data found for wallet '{address}' in category '{category}'` |
| Wallet exists but no category data (categories list endpoint) | `200` | Returns `{"wallet": "...", "categories": []}` — empty list, not an error |

### 8.2 Rationale for 404 on Invalid Category

Invalid categories return `404` (not `422` or `400`) because:
- The category is a path parameter that references a resource (leaderboard for that category)
- If the category doesn't exist, the resource is not found
- This is consistent with how other path-parameter-not-found cases are handled in the existing API

### 8.3 Empty States

| Endpoint | Empty State Behaviour |
|---|---|
| `GET /leaderboard/{category}` | Returns `{"category": "...", "data": [], "limit": 50, "offset": 0}` — empty `data` array |
| `GET /leaderboard/{category}/specialists` | Same — empty `data` array |
| `GET /wallets/{address}/categories` | Returns `{"wallet": "...", "categories": []}` — empty `categories` array |
| `GET /wallets/{address}/categories/{category}` | Returns `404` — wallet+category combo not found |

---

## 9. Test Plan

### 9.1 Unit Tests (Mock-based, in `app/tests/test_api/`)

Add to the existing `test_endpoints.py`:

| Test | Description |
|---|---|
| `test_category_leaderboard_valid` | `GET /api/v1/leaderboard/politics` returns 200 with correct shape |
| `test_category_leaderboard_invalid` | `GET /api/v1/leaderboard/invalid` returns 404 |
| `test_category_leaderboard_specialists` | `GET /api/v1/leaderboard/politics/specialists` returns 200 with entries |
| `test_category_leaderboard_params` | `?limit=10&offset=5` applied correctly |
| `test_wallet_categories_valid` | `GET /api/v1/wallets/0xabc/` returns categories list |
| `test_wallet_categories_wallet_not_found` | Returns 404 for unknown wallet |
| `test_wallet_category_detail_valid` | Returns 200 with full detail |
| `test_wallet_category_detail_not_found` | Returns 404 when no data for combo |
| `test_wallet_category_detail_invalid_category` | Returns 404 for invalid category |
| `test_wallet_profile_includes_categories` | Existing `WalletProfile` endpoint now includes `categories` |

### 9.2 Mock Data

Add to `app/tests/conftest.py`:

```python
class MockCategoryRanking:
    """Minimal mock that mimics CategoryRanking ORM attributes."""
    def __init__(self, rank, wallet, wallet_score=0.85, roi=41.29,
                 win_rate=0.62, total_pnl=37053.07, num_trades=840,
                 total_volume=89730.34):
        self.rank = rank
        self.wallet = wallet
        self.wallet_score = wallet_score
        self.roi = roi
        self.win_rate = win_rate
        self.total_pnl = total_pnl
        self.num_trades = num_trades
        self.total_volume = total_volume
```

### 9.3 Integration Tests (in `app/tests/test_db_integrity.py`)

Add integration tests that verify:
- `category_rankings` row count ≥ 50
- `category_analytics` row count ≥ 100
- FK: `category_analytics.wallet` → `wallets.wallet`
- FK: `category_rankings.wallet` → `wallets.wallet`
- Not-null: `wallet`, `category`, `snapshot_date` in both tables
- Analytics quality: ROI bounds, win_rate in [0,1]
- Cross-table: wallets in `category_analytics` exist in `wallets`

---

## 10. Implementation Order

The following order minimises blocking dependencies:

| Step | Files | Depends On |
|---|---|---|
| 1 | `app/models/schemas.py` — add 5 new Pydantic models + update `WalletProfile` | Nothing |
| 2 | `app/utils/category.py` — create validation utility | Step 1 (`MarketCategory` enum already exists) |
| 3 | `app/services/category_service.py` — create service with 4 functions | Step 1, `CategoryAnalytic` + `CategoryRanking` ORM models |
| 4 | `app/api/v1/categories.py` — create router with 4 endpoints | Steps 1–3 |
| 5 | `app/api/router.py` — register categories router | Step 4 |
| 6 | `app/api/v1/wallets.py` — update to include categories in profile | Steps 1, 3 |
| 7 | `app/tests/conftest.py` — add mock helpers | Step 1 |
| 8 | `app/tests/test_api/test_endpoints.py` — add 10 new tests | Steps 1–6 |
| 9 | `app/tests/test_db_integrity.py` — add integration tests | DB with category tables populated |

### Testable After Each Step

- After Step 2: `python3 -m pytest app/tests/test_api/ -k "category"` (unit tests for validation)
- After Step 6: `python3 -m pytest app/tests/test_api/ -v` (all 19+ endpoint tests pass)
- After Step 9: `python3 -m pytest app/tests/ -v` (all tests, including integration)

---

## Appendix A: Existing SQLAlchemy Models (for reference)

These models must exist in `app/db/models.py` before the service layer can be implemented. They are created by the Phase 2 DB schema migration (separate spec):

```python
class CategoryAnalytic(Base):
    __tablename__ = "category_analytics"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    category = Column(Text, primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    num_trades = Column(Integer, nullable=True)
    total_volume = Column(Numeric(28, 2), nullable=True)
    total_cost_basis = Column(Numeric(28, 2), nullable=True)
    total_pnl = Column(Numeric(28, 2), nullable=True)
    total_realized_pnl = Column(Numeric(28, 2), nullable=True)
    total_unrealized_pnl = Column(Numeric(28, 2), nullable=True)
    roi = Column(Numeric(8, 6), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    num_resolved_positions = Column(Integer, nullable=True)
    profit_factor = Column(Numeric(28, 6), nullable=True)
    avg_position_size = Column(Numeric(28, 2), nullable=True)
    avg_holding_duration = Column(Interval, nullable=True)
    is_specialist = Column(Boolean, nullable=False, default=False)
    category_rank = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_cat_analytics_snapshot_cat_rank", "snapshot_date", "category", "category_rank"),
        Index("idx_cat_analytics_wallet", "wallet", "snapshot_date"),
    )


class CategoryRanking(Base):
    __tablename__ = "category_rankings"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    category = Column(Text, primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    list_type = Column(Text, primary_key=True)
    rank = Column(Integer, nullable=False)
    wallet_score = Column(Numeric(8, 6), nullable=True)
    roi = Column(Numeric(8, 6), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    total_pnl = Column(Numeric(28, 2), nullable=True)
    num_trades = Column(Integer, nullable=True)
    total_volume = Column(Numeric(28, 2), nullable=True)

    __table_args__ = (
        Index("idx_cat_rankings_date_cat_list_rank", "snapshot_date", "category", "list_type", "rank"),
    )
```

---

## Appendix B: Full File Index

| Action | File |
|---|---|
| **CREATE** | `app/api/v1/categories.py` |
| **CREATE** | `app/services/category_service.py` |
| **CREATE** | `app/utils/category.py` |
| **MODIFY** | `app/models/schemas.py` — add 5 new classes, update `WalletProfile` |
| **MODIFY** | `app/api/router.py` — import + register categories router |
| **MODIFY** | `app/api/v1/wallets.py` — add categories to wallet profile response |
| **MODIFY** | `app/tests/conftest.py` — add `MockCategoryRanking` |
| **MODIFY** | `app/tests/test_api/test_endpoints.py` — add 10 new tests |
| **MODIFY** | `app/tests/test_db_integrity.py` — add category integration tests |
