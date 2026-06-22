# Phase 2 — API Endpoints: Category Analytics

> **Goal**: Expose per-category wallet analytics and category-specific leaderboards via the API.
> **Status**: Planning — ready for spec.

---

## 1. New Endpoints

### `GET /api/v1/leaderboard/{category}` — Category Leaderboard

Top traders in a specific category, ranked by ROI.

**Path parameter**:
- `category` — one of `politics`, `crypto`, `sports`, `economics`, `technology`, `ai`, `geopolitics`, `entertainment`

**Query parameters**:
- `limit` (int, default 50, max 200) — number of entries
- `offset` (int, default 0) — pagination offset

**Response** (200):

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

**Response** (404): If category is not one of the 8 valid categories.

---

### `GET /api/v1/leaderboard/{category}/specialists` — Category Specialists

Top traders flagged as specialists in a category.

Same response shape as the main category leaderboard, but only includes wallets where `is_specialist = True`.

---

### `GET /api/v1/wallets/{address}/categories` — Wallet Category Breakdown

Per-category performance breakdown for a specific wallet.

**Response** (200):

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
    },
    {
      "category": "crypto",
      "num_trades": 42,
      "total_volume": 12300.00,
      "total_pnl": -420.00,
      "roi": -3.41,
      "win_rate": 0.45,
      "profit_factor": null,
      "avg_position_size": 292.86,
      "is_specialist": false,
      "category_rank": null
    }
  ]
}
```

**Response** (404): If wallet address does not exist.

---

### `GET /api/v1/wallets/{address}/categories/{category}` — Single Category Detail

Detail for a specific wallet + category combination.

**Response** (200):

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

**Response** (404): If wallet or category not found.

---

## 2. Schema Updates

### New Pydantic Models in `app/models/schemas.py`

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

class CategoryLeaderboardResponse(BaseModel):
    category: str
    data: list[CategoryLeaderboardEntry]
    limit: int
    offset: int

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

class WalletCategoryResponse(BaseModel):
    wallet: str
    categories: list[WalletCategorySummary]

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
```

---

## 3. Service Layer

### `app/services/category_service.py` (NEW)

```python
async def get_category_leaderboard(
    db: AsyncSession, category: str, limit: int = 50, offset: int = 0
) -> list[CategoryRanking]:
    """Top traders in a category from category_rankings."""

async def get_category_specialists(
    db: AsyncSession, category: str, limit: int = 50
) -> list[CategoryRanking]:
    """Specialists in a category."""

async def get_wallet_categories(
    db: AsyncSession, address: str
) -> list[CategoryAnalytic]:
    """All category analytics for a wallet."""

async def get_wallet_category_detail(
    db: AsyncSession, address: str, category: str
) -> Optional[CategoryAnalytic]:
    """Single category detail for a wallet."""
```

---

## 4. Router

### `app/api/v1/categories.py` (NEW)

```python
router = APIRouter()

@router.get("/leaderboard/{category}", response_model=CategoryLeaderboardResponse)
async def category_leaderboard(...): ...

@router.get("/leaderboard/{category}/specialists", response_model=CategoryLeaderboardResponse)
async def category_specialists(...): ...

@router.get("/wallets/{address}/categories", response_model=WalletCategoryResponse)
async def wallet_categories(...): ...

@router.get("/wallets/{address}/categories/{category}", response_model=CategoryDetailResponse)
async def wallet_category_detail(...): ...
```

### `app/api/router.py` — Registration

```python
from app.api.v1.categories import router as categories_router

api_router.include_router(categories_router, prefix="/api/v1", tags=["categories"])
```

---

## 5. Update Existing Wallet Profile

Add a `categories` field to `WalletProfile` in `app/models/schemas.py`:

```python
class WalletProfile(BaseModel):
    # ... existing fields ...
    categories: list[WalletCategorySummary] = []  # NEW
    # ... existing fields ...
```

Update `app/services/wallet_service.py` to populate this field when fetching a wallet profile.

---

## 6. Acceptance Criteria

- [ ] `GET /api/v1/leaderboard/politics` returns top 50 politics traders with correct fields
- [ ] `GET /api/v1/leaderboard/sports/specialists` returns only specialists
- [ ] `GET /api/v1/leaderboard/invalid` returns 404
- [ ] `GET /api/v1/wallets/0x.../categories` returns per-category breakdown
- [ ] `GET /api/v1/wallets/0x.../categories/politics` returns single category detail
- [ ] `GET /api/v1/wallets/0xDEAD.../categories` returns 404 for unknown wallet
- [ ] Existing wallet profile endpoint includes `categories` field
- [ ] All responses use correct JSON field names (snake_case)
- [ ] Pagination (limit/offset) works correctly
- [ ] Existing 41 tests still pass
