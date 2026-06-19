# Phase 2 — Testing Strategy Implementation Spec

> **Version**: 1.0  
> **Target**: 26 new tests (8 API + 8 integration + 10 classifier)  
> **Total after Phase 2**: 67 tests  
> **Pattern**: Mirrors Phase 1 test structure exactly

---

## Table of Contents

1. [Prerequisites / Source Code Dependencies](#1-prerequisites--source-code-dependencies)
2. [File Manifest](#2-file-manifest)
3. [Category Schema (for reference)](#3-category-schema-for-reference)
4. [`test_category_endpoints.py` — 8 API Tests](#4-appteststest_apitest_category_endpointspy--8-api-tests)
5. [`conftest.py` — Updated Shared Fixtures](#5-conftestpy--updated-shared-fixtures)
6. [`test_db_integrity.py` — 8 New Integration Tests](#6-test_db_integritypy--8-new-integration-tests)
7. [`test_category_classifier.py` — 10 Classifier Unit Tests](#7-appteststest_category_classifierpy--10-classifier-unit-tests)
8. [Edge Cases Not Covered by Tests](#8-edge-cases-not-covered-by-tests)
9. [How to Run](#9-how-to-run)
10. [Acceptance Checklist](#10-acceptance-checklist)

---

## 1. Prerequisites / Source Code Dependencies

Before these tests can pass, the following source code must exist:

### 1.1 DB Models (`app/db/models.py`)

Add two new ORM models **after** `RankingSnapshot`:

```python
class CategoryAnalytic(Base):
    __tablename__ = "category_analytics"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    category = Column(Text, primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    total_pnl = Column(Numeric(28, 2), nullable=True)
    total_realized_pnl = Column(Numeric(28, 2), nullable=True)
    total_unrealized_pnl = Column(Numeric(28, 2), nullable=True)
    roi = Column(Numeric(8, 6), nullable=True)
    total_volume = Column(Numeric(28, 2), nullable=True)
    total_cost_basis = Column(Numeric(28, 2), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    num_trades = Column(Integer, nullable=True)
    num_resolved_positions = Column(Integer, nullable=True)
    profit_factor = Column(Numeric(28, 6), nullable=True)
    sharpe_ratio = Column(Numeric(8, 6), nullable=True)
    max_drawdown = Column(Numeric(8, 6), nullable=True)
    avg_position_size = Column(Numeric(28, 2), nullable=True)
    avg_holding_duration = Column(Interval, nullable=True)
    wallet_score = Column(Numeric(8, 6), nullable=True)
    is_specialist = Column(Boolean, nullable=False, server_default=text("false"))
    num_trades_in_category = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_cat_analytics_wallet", "wallet"),
        Index("idx_cat_analytics_category", "category"),
        Index("idx_cat_analytics_date_score", "snapshot_date", text("wallet_score DESC NULLS LAST")),
    )


class CategoryRanking(Base):
    __tablename__ = "category_rankings"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    category = Column(Text, primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    rank = Column(Integer, nullable=False)
    wallet_score = Column(Numeric(8, 6), nullable=True)
    roi = Column(Numeric(8, 6), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    num_trades = Column(Integer, nullable=True)
    total_pnl = Column(Numeric(28, 2), nullable=True)
    is_specialist = Column(Boolean, nullable=False, server_default=text("false"))
    specialist_rank = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_cat_rankings_category_rank", "category", "rank"),
        Index("idx_cat_rankings_snapshot", "snapshot_date", "category"),
    )
```

### 1.2 Pydantic Schemas (`app/models/schemas.py`)

Add these response models:

```python
class CategoryAnalyticsData(BaseModel):
    category: str
    total_pnl: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    num_trades: Optional[int] = None
    total_volume: Optional[Decimal] = None
    wallet_score: Optional[Decimal] = None
    is_specialist: bool = False
    num_trades_in_category: Optional[int] = None

    model_config = {"from_attributes": True}


class CategoryLeaderboardEntry(BaseModel):
    rank: int
    wallet: str
    score: Decimal
    roi: Decimal
    win_rate: Decimal
    total_pnl: Decimal
    num_trades: int
    is_specialist: bool = False

    model_config = {"from_attributes": True}


class CategoryLeaderboardResponse(BaseModel):
    data: list[CategoryLeaderboardEntry]
    limit: int
    offset: int
    category: str


class WalletCategoryBreakdown(BaseModel):
    wallet: str
    categories: list[CategoryAnalyticsData]
    total_categories: int
```

### 1.3 Service Layer (`app/services/category_service.py`)

New file with these functions (same pattern as `leaderboard_service.py` and `wallet_service.py`):

```python
# Expected signatures:
async def get_category_leaderboard(
    db: AsyncSession, category: str, limit: int = 100, offset: int = 0
) -> list[CategoryRanking]: ...

async def get_category_specialists(
    db: AsyncSession, category: str, limit: int = 20
) -> list[CategoryRanking]: ...

async def get_wallet_categories(
    db: AsyncSession, address: str
) -> list[CategoryAnalytic]: ...

async def get_wallet_category_detail(
    db: AsyncSession, address: str, category: str
) -> Optional[CategoryAnalytic]: ...
```

### 1.4 Router (`app/api/v1/categories.py`)

New router file. The tests assume these routes exist:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db
from app.models.schemas import (
    CategoryAnalyticsData,
    CategoryLeaderboardEntry,
    CategoryLeaderboardResponse,
    WalletCategoryBreakdown,
)
from app.services.category_service import (
    get_category_leaderboard,
    get_category_specialists,
    get_wallet_categories,
    get_wallet_category_detail,
)
from app.models.enums import MarketCategory

router = APIRouter()

VALID_CATEGORIES = {c.value for c in MarketCategory}


@router.get("/{category}", response_model=CategoryLeaderboardResponse)
async def category_leaderboard(
    category: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CategoryLeaderboardResponse: ...


@router.get("/{category}/specialists", response_model=list[CategoryLeaderboardEntry])
async def category_specialists(
    category: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryLeaderboardEntry]: ...


@router.get("/wallets/{address}/categories", response_model=WalletCategoryBreakdown)
async def wallet_categories(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletCategoryBreakdown: ...


@router.get("/wallets/{address}/categories/{category}", response_model=CategoryAnalyticsData)
async def wallet_category_detail(
    address: str,
    category: str,
    db: AsyncSession = Depends(get_db),
) -> CategoryAnalyticsData: ...
```

### 1.5 Router Registration (`app/api/router.py`)

```python
# Add to existing imports:
from app.api.v1.categories import router as categories_router

# Add after existing include_routers:
api_router.include_router(categories_router, prefix="/leaderboard", tags=["categories"])
api_router.include_router(categories_router, prefix="/wallets", tags=["categories"])
```

Note: The categories router is mounted under two prefixes to support both `/api/v1/leaderboard/{category}` and `/api/v1/wallets/{address}/categories/...` paths.

### 1.6 Category DB Migrations

A new Alembic migration (e.g., `002_add_category_tables.py`) must create both `category_analytics` and `category_rankings` tables. See §3 for full schema.

### 1.7 Classifier Module (`app/services/category_classifier.py`)

```python
# Expected interface:
from app.models.enums import MarketCategory

CATEGORY_KEYWORDS: dict[MarketCategory, list[str]] = { ... }

def infer_category(question: str) -> MarketCategory | None:
    """Classify a market question into one of the MarketCategory values.
    
    Returns None if the question doesn't match any known category.
    Case-insensitive matching against keyword lists.
    """
    ...
```

---

## 2. File Manifest

| File | Action | Description |
|------|--------|-------------|
| `app/tests/test_api/test_category_endpoints.py` | **CREATE** | 8 mock-based API tests for category endpoints |
| `app/tests/conftest.py` | **UPDATE** | Add shared fixtures for CategoryRanking/CategoryAnalytic mocks |
| `app/tests/test_db_integrity.py` | **UPDATE** | Add 8 new integration tests for category tables |
| `app/tests/test_category_classifier.py` | **CREATE** | 10 pure unit tests for `infer_category()` |
| `.opencode/specs/phase-02-testing.spec.md` | **CREATE** | This document |

---

## 3. Category Schema (for reference)

### `category_analytics`

| Column | Type | Constraints |
|--------|------|-------------|
| `wallet` | TEXT | PK, FK → wallets.wallet |
| `category` | TEXT | PK |
| `snapshot_date` | DATE | PK |
| `total_pnl` | NUMERIC(28,2) | nullable |
| `total_realized_pnl` | NUMERIC(28,2) | nullable |
| `total_unrealized_pnl` | NUMERIC(28,2) | nullable |
| `roi` | NUMERIC(8,6) | nullable |
| `total_volume` | NUMERIC(28,2) | nullable |
| `total_cost_basis` | NUMERIC(28,2) | nullable |
| `win_rate` | NUMERIC(8,6) | nullable |
| `num_trades` | INTEGER | nullable |
| `num_resolved_positions` | INTEGER | nullable |
| `profit_factor` | NUMERIC(28,6) | nullable |
| `sharpe_ratio` | NUMERIC(8,6) | nullable |
| `max_drawdown` | NUMERIC(8,6) | nullable |
| `avg_position_size` | NUMERIC(28,2) | nullable |
| `avg_holding_duration` | INTERVAL | nullable |
| `wallet_score` | NUMERIC(8,6) | nullable |
| `is_specialist` | BOOLEAN | NOT NULL, default false |
| `num_trades_in_category` | INTEGER | nullable |

### `category_rankings`

| Column | Type | Constraints |
|--------|------|-------------|
| `wallet` | TEXT | PK, FK → wallets.wallet |
| `category` | TEXT | PK |
| `snapshot_date` | DATE | PK |
| `rank` | INTEGER | NOT NULL |
| `wallet_score` | NUMERIC(8,6) | nullable |
| `roi` | NUMERIC(8,6) | nullable |
| `win_rate` | NUMERIC(8,6) | nullable |
| `num_trades` | INTEGER | nullable |
| `total_pnl` | NUMERIC(28,2) | nullable |
| `is_specialist` | BOOLEAN | NOT NULL, default false |
| `specialist_rank` | INTEGER | nullable |

---

## 4. `app/tests/test_api/test_category_endpoints.py` — 8 API Tests

### 4.1 Imports and Module-Level Setup

```python
"""Mock-based tests for category analytics endpoints.

Pattern: httpx.AsyncClient + ASGITransport with mocked DB sessions.
All tests use @pytest.mark.asyncio and the shared `client` fixture
from conftest.py.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.api.dependencies import get_db
from app.db.models import CategoryAnalytic, CategoryRanking
from app.main import app
```

### 4.2 Helper: Build Mock Objects

```python
# ── Helper factory functions ──────────────────────────────────────────

def make_mock_category_ranking(
    wallet: str = "0xabc123def456",
    category: str = "Politics",
    rank: int = 1,
    score: Decimal = Decimal("85.5"),
    roi: Decimal = Decimal("45.2"),
    win_rate: Decimal = Decimal("0.72"),
    total_pnl: Decimal = Decimal("12500.00"),
    num_trades: int = 45,
    is_specialist: bool = False,
    specialist_rank: int | None = None,
) -> MagicMock:
    """Create a MagicMock that behaves like a CategoryRanking ORM row."""
    mock = MagicMock(spec=CategoryRanking)
    mock.wallet = wallet
    mock.category = category
    mock.rank = rank
    mock.wallet_score = score
    mock.roi = roi
    mock.win_rate = win_rate
    mock.total_pnl = total_pnl
    mock.num_trades = num_trades
    mock.is_specialist = is_specialist
    mock.specialist_rank = specialist_rank
    return mock


def make_mock_category_analytic(
    wallet: str = "0xabc123def456",
    category: str = "Politics",
    total_pnl: Decimal = Decimal("12500.00"),
    roi: Decimal = Decimal("45.2"),
    win_rate: Decimal = Decimal("0.72"),
    num_trades: int = 45,
    total_volume: Decimal = Decimal("50000.00"),
    wallet_score: Decimal = Decimal("85.5"),
    is_specialist: bool = False,
    num_trades_in_category: int = 45,
) -> MagicMock:
    """Create a MagicMock that behaves like a CategoryAnalytic ORM row."""
    mock = MagicMock(spec=CategoryAnalytic)
    mock.wallet = wallet
    mock.category = category
    mock.total_pnl = total_pnl
    mock.roi = roi
    mock.win_rate = win_rate
    mock.num_trades = num_trades
    mock.total_volume = total_volume
    mock.wallet_score = wallet_score
    mock.is_specialist = is_specialist
    mock.num_trades_in_category = num_trades_in_category
    return mock
```

### 4.3 Fixture: Custom Mock Session

```python
@pytest.fixture
def category_mock_session() -> AsyncMock:
    """Create a mock DB session pre-configured for category endpoint tests.

    Tests override `.execute` return values before injecting.
    """
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
def override_db(category_mock_session: AsyncMock) -> None:
    """Override the get_db dependency with a mock session.
    
    This fixture is autouse=False so each test can decide whether to use it.
    """
    async def _override() -> AsyncMock:
        yield category_mock_session

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()
```

### 4.4 Test Functions

```python
# ═══════════════════════════════════════════════════════════════════════
# 1. Category Leaderboard - Valid
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_category_leaderboard_valid(
    client: AsyncClient,
    category_mock_session: AsyncMock,
    override_db: None,
) -> None:
    """GET /api/v1/leaderboard/politics returns 200 with correct shape."""
    # Arrange: configure mock to return realistic ranking data
    mock_entries = [
        make_mock_category_ranking(
            wallet="0xabc1", rank=1, score=Decimal("95.2"),
            roi=Decimal("120.5"), win_rate=Decimal("0.85"),
            total_pnl=Decimal("50000"), num_trades=120,
        ),
        make_mock_category_ranking(
            wallet="0xabc2", rank=2, score=Decimal("82.1"),
            roi=Decimal("65.3"), win_rate=Decimal("0.72"),
            total_pnl=Decimal("25000"), num_trades=80,
        ),
        make_mock_category_ranking(
            wallet="0xabc3", rank=3, score=Decimal("71.8"),
            roi=Decimal("32.0"), win_rate=Decimal("0.60"),
            total_pnl=Decimal("10000"), num_trades=55,
        ),
    ]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = mock_entries
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    category_mock_session.execute.return_value = mock_result

    # Act
    response = await client.get("/api/v1/leaderboard/politics")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["category"] == "politics"
    assert data["limit"] == 100
    assert data["offset"] == 0
    assert len(data["data"]) == 3

    # Verify first entry shape
    first = data["data"][0]
    assert first["rank"] == 1
    assert first["wallet"] == "0xabc1"
    assert float(first["score"]) == pytest.approx(95.2)
    assert float(first["roi"]) == pytest.approx(120.5)
    assert float(first["win_rate"]) == pytest.approx(0.85)
    assert float(first["total_pnl"]) == pytest.approx(50000)
    assert first["num_trades"] == 120
    assert "is_specialist" in first


# ═══════════════════════════════════════════════════════════════════════
# 2. Category Leaderboard - Invalid Category
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_category_leaderboard_invalid_category(
    client: AsyncClient,
) -> None:
    """GET /api/v1/leaderboard/invalid returns 404."""
    response = await client.get("/api/v1/leaderboard/invalid")
    assert response.status_code == 404
    detail = response.json().get("detail", "")
    assert "category" in detail.lower() or "not found" in detail.lower() or "invalid" in detail.lower()


# ═══════════════════════════════════════════════════════════════════════
# 3. Category Leaderboard - With Params
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_category_leaderboard_with_params(
    client: AsyncClient,
    category_mock_session: AsyncMock,
    override_db: None,
) -> None:
    """GET /api/v1/leaderboard/crypto?limit=5&offset=10 respects params."""
    # Arrange: return a single entry (limit 5 is respected downstream)
    mock_entries = [
        make_mock_category_ranking(
            wallet="0xcrypto1", rank=1, score=Decimal("99.9"),
            roi=Decimal("250.0"), win_rate=Decimal("0.90"),
            total_pnl=Decimal("100000"), num_trades=200,
        ),
    ]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = mock_entries
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    category_mock_session.execute.return_value = mock_result

    # Act
    response = await client.get("/api/v1/leaderboard/crypto?limit=5&offset=10")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 5
    assert data["offset"] == 10
    assert data["category"] == "crypto"
    assert len(data["data"]) == 1


# ═══════════════════════════════════════════════════════════════════════
# 4. Category Specialists
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_category_specialists(
    client: AsyncClient,
    category_mock_session: AsyncMock,
    override_db: None,
) -> None:
    """GET /api/v1/leaderboard/crypto/specialists returns specialists."""
    # Arrange
    mock_entries = [
        make_mock_category_ranking(
            wallet="0xspex1", rank=1, score=Decimal("98.0"),
            roi=Decimal("300.0"), win_rate=Decimal("0.95"),
            total_pnl=Decimal("200000"), num_trades=350,
            is_specialist=True, specialist_rank=1,
        ),
        make_mock_category_ranking(
            wallet="0xspex2", rank=2, score=Decimal("85.0"),
            roi=Decimal("150.0"), win_rate=Decimal("0.80"),
            total_pnl=Decimal("75000"), num_trades=180,
            is_specialist=True, specialist_rank=2,
        ),
    ]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = mock_entries
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    category_mock_session.execute.return_value = mock_result

    # Act
    response = await client.get("/api/v1/leaderboard/crypto/specialists")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    specialist = data[0]
    assert specialist["rank"] == 1
    assert specialist["is_specialist"] is True
    assert specialist["wallet"] == "0xspex1"

    # Verify all expected keys are present
    for entry in data:
        for key in ("rank", "wallet", "score", "roi", "win_rate",
                     "total_pnl", "num_trades", "is_specialist"):
            assert key in entry, f"Missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════
# 5. Wallet Categories
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_wallet_categories(
    client: AsyncClient,
    category_mock_session: AsyncMock,
    override_db: None,
) -> None:
    """GET /api/v1/wallets/0xwallet/categories returns breakdown."""
    # Arrange
    mock_analytics = [
        make_mock_category_analytic(
            wallet="0xwallet", category="Politics",
            total_pnl=Decimal("5000"), roi=Decimal("25.0"),
            win_rate=Decimal("0.65"), num_trades=30,
            total_volume=Decimal("20000"), wallet_score=Decimal("72.3"),
            is_specialist=False, num_trades_in_category=30,
        ),
        make_mock_category_analytic(
            wallet="0xwallet", category="Crypto",
            total_pnl=Decimal("15000"), roi=Decimal("80.0"),
            win_rate=Decimal("0.78"), num_trades=55,
            total_volume=Decimal("80000"), wallet_score=Decimal("88.1"),
            is_specialist=True, num_trades_in_category=55,
        ),
        make_mock_category_analytic(
            wallet="0xwallet", category="Sports",
            total_pnl=Decimal("-1000"), roi=Decimal("-5.0"),
            win_rate=Decimal("0.45"), num_trades=12,
            total_volume=Decimal("5000"), wallet_score=Decimal("45.0"),
            is_specialist=False, num_trades_in_category=12,
        ),
    ]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = mock_analytics
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = MagicMock()  # wallet exists
    category_mock_session.execute.return_value = mock_result

    # Act
    response = await client.get("/api/v1/wallets/0xwallet/categories")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["wallet"] == "0xwallet"
    assert data["total_categories"] == 3
    assert len(data["categories"]) == 3

    # Verify individual category entries
    cat_map = {c["category"]: c for c in data["categories"]}
    assert "Politics" in cat_map
    assert "Crypto" in cat_map
    assert "Sports" in cat_map

    crypto = cat_map["Crypto"]
    assert float(crypto["total_pnl"]) == pytest.approx(15000)
    assert float(crypto["roi"]) == pytest.approx(80.0)
    assert float(crypto["win_rate"]) == pytest.approx(0.78)
    assert crypto["num_trades"] == 55
    assert crypto["is_specialist"] is True
    assert crypto["num_trades_in_category"] == 55


# ═══════════════════════════════════════════════════════════════════════
# 6. Wallet Categories - Not Found
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_wallet_categories_not_found(
    client: AsyncClient,
    category_mock_session: AsyncMock,
    override_db: None,
) -> None:
    """GET /api/v1/wallets/0xnonexistent/categories returns 404."""
    # Arrange: wallet doesn't exist
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    category_mock_session.execute.return_value = mock_result

    # Act
    response = await client.get("/api/v1/wallets/0xnonexistent/categories")

    # Assert
    assert response.status_code == 404
    detail = response.json().get("detail", "")
    assert "wallet" in detail.lower() or "not found" in detail.lower()


# ═══════════════════════════════════════════════════════════════════════
# 7. Wallet Category Detail
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_wallet_category_detail(
    client: AsyncClient,
    category_mock_session: AsyncMock,
    override_db: None,
) -> None:
    """GET /api/v1/wallets/0xwallet/categories/Politics returns detail."""
    # Arrange
    mock_analytic = make_mock_category_analytic(
        wallet="0xwallet", category="Politics",
        total_pnl=Decimal("5000"), roi=Decimal("25.0"),
        win_rate=Decimal("0.65"), num_trades=30,
        total_volume=Decimal("20000"), wallet_score=Decimal("72.3"),
        is_specialist=False, num_trades_in_category=30,
    )
    # Configure the mock to return the analytic for scalar_one_or_none
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_analytic
    category_mock_session.execute.return_value = mock_result

    # Act
    response = await client.get("/api/v1/wallets/0xwallet/categories/Politics")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Politics"
    assert float(data["total_pnl"]) == pytest.approx(5000)
    assert float(data["roi"]) == pytest.approx(25.0)
    assert float(data["win_rate"]) == pytest.approx(0.65)
    assert data["num_trades"] == 30
    assert float(data["total_volume"]) == pytest.approx(20000)
    assert float(data["wallet_score"]) == pytest.approx(72.3)
    assert data["is_specialist"] is False


# ═══════════════════════════════════════════════════════════════════════
# 8. Wallet Category Detail - Not Found
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_wallet_category_detail_not_found(
    client: AsyncClient,
    category_mock_session: AsyncMock,
    override_db: None,
) -> None:
    """GET /api/v1/wallets/0xwallet/categories/Unknown returns 404."""
    # Arrange: wallet exists but category not found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    category_mock_session.execute.return_value = mock_result

    # Act
    response = await client.get("/api/v1/wallets/0xwallet/categories/Unknown")

    # Assert
    assert response.status_code == 404
    detail = response.json().get("detail", "")
    assert "category" in detail.lower() or "not found" in detail.lower()
```

### 4.5 Import Path Notes

The tests above assume:

- `from app.api.dependencies import get_db` — already exists (confirmed)
- `from app.db.models import CategoryAnalytic, CategoryRanking` — to be added in Phase 2
- `from app.main import app` — already exists
- `client` fixture from `conftest.py` — already exists, uses `ASGITransport` + dependency override

---

## 5. `conftest.py` — Updated Shared Fixtures

### 5.1 Changes to Existing File

The existing `conftest.py` is 38 lines. The updates append new fixture factories **after** the existing `client` fixture and do NOT modify any existing code.

### 5.2 Full Updated Content

```python
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_db
from app.db.models import CategoryAnalytic, CategoryRanking
from app.main import app


# ── Phase 1: Base mock session factory ────────────────────────────────

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


# ── Phase 2: Category test mock factories ─────────────────────────────

def make_mock_category_ranking(
    wallet: str = "0xabc123def456",
    category: str = "Politics",
    rank: int = 1,
    score: Decimal = Decimal("85.5"),
    roi: Decimal = Decimal("45.2"),
    win_rate: Decimal = Decimal("0.72"),
    total_pnl: Decimal = Decimal("12500.00"),
    num_trades: int = 45,
    is_specialist: bool = False,
    specialist_rank: int | None = None,
) -> MagicMock:
    """Create a MagicMock that behaves like a CategoryRanking ORM row."""
    mock = MagicMock(spec=CategoryRanking)
    mock.wallet = wallet
    mock.category = category
    mock.rank = rank
    mock.wallet_score = score
    mock.roi = roi
    mock.win_rate = win_rate
    mock.total_pnl = total_pnl
    mock.num_trades = num_trades
    mock.is_specialist = is_specialist
    mock.specialist_rank = specialist_rank
    return mock


def make_mock_category_analytic(
    wallet: str = "0xabc123def456",
    category: str = "Politics",
    total_pnl: Decimal = Decimal("12500.00"),
    roi: Decimal = Decimal("45.2"),
    win_rate: Decimal = Decimal("0.72"),
    num_trades: int = 45,
    total_volume: Decimal = Decimal("50000.00"),
    wallet_score: Decimal = Decimal("85.5"),
    is_specialist: bool = False,
    num_trades_in_category: int = 45,
) -> MagicMock:
    """Create a MagicMock that behaves like a CategoryAnalytic ORM row."""
    mock = MagicMock(spec=CategoryAnalytic)
    mock.wallet = wallet
    mock.category = category
    mock.total_pnl = total_pnl
    mock.roi = roi
    mock.win_rate = win_rate
    mock.num_trades = num_trades
    mock.total_volume = total_volume
    mock.wallet_score = wallet_score
    mock.is_specialist = is_specialist
    mock.num_trades_in_category = num_trades_in_category
    return mock


def make_category_mock_session(
    ranking_entries: list[MagicMock] | None = None,
    analytic_entries: list[MagicMock] | None = None,
    scalar_one_return: MagicMock | None = None,
) -> AsyncMock:
    """Create a mock DB session pre-loaded with category test data.

    Args:
        ranking_entries: Results for .scalars().all() — used by leaderboard queries.
        analytic_entries: Alternative results for .all() — used by wallet breakdown queries.
        scalar_one_return: Result for .scalar_one_or_none() — used by detail queries.

    Returns:
        Configured AsyncMock session.
    """
    session = AsyncMock()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ranking_entries or []

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = scalar_one_return
    mock_result.all.return_value = analytic_entries or []

    session.execute = AsyncMock(return_value=mock_result)
    return session
```

### 5.3 Summary of Changes

| What | Detail |
|------|--------|
| New imports | `Decimal`, `CategoryAnalytic`, `CategoryRanking` |
| New factories | `make_mock_category_ranking()`, `make_mock_category_analytic()`, `make_category_mock_session()` |
| Existing code | Untouched — `make_mock_session()` and `client` fixture remain identical |

---

## 6. `test_db_integrity.py` — 8 New Integration Tests

### 6.1 Additions to Existing File

The 8 new tests are **appended after the last existing test** (`test_markets_have_at_least_one_outcome`, line 268). The module-level constants and fixtures are also extended.

### 6.2 Updated Constants

Add these entries at module level (after the existing constants):

```python
# ── Phase 2: Category table thresholds ────────────────────────────────
CATEGORY_THRESHOLDS = {
    "category_analytics": 100,
    "category_rankings": 50,
}

CATEGORY_EMPTY_TABLES: set[str] = set()  # both should be populated

CATEGORY_FK_CHECKS = [
    ("category_analytics", "wallets", "wallet", "wallet"),
    ("category_rankings", "wallets", "wallet", "wallet"),
]

CATEGORY_NOT_NULL_COLS = [
    ("category_analytics", "wallet"),
    ("category_analytics", "category"),
    ("category_analytics", "snapshot_date"),
]
```

### 6.3 New Test Functions

```python
# ═════════════════════════════════════════════════════════════════════════
# Phase 2 — Category Analytics & Rankings
# ═════════════════════════════════════════════════════════════════════════

@ pytest.mark.parametrize(
    "tbl,min_rows",
    list(CATEGORY_THRESHOLDS.items()),
    ids=[f"{t} ≥ {r}" for t, r in CATEGORY_THRESHOLDS.items()],
)
def test_category_table_row_counts(
    conn: Connection, tbl: str, min_rows: int
) -> None:
    """Phase 2: Category tables meet minimum row thresholds."""
    count: int = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
    assert count >= min_rows, (
        f"{tbl} has {count} rows, expected at least {min_rows}"
    )


@ pytest.mark.parametrize(
    ("child_tbl", "parent_tbl", "child_col", "parent_col"),
    CATEGORY_FK_CHECKS,
    ids=[f"{c}.{cc} → {p}.{pc}" for c, p, cc, pc in CATEGORY_FK_CHECKS],
)
def test_category_referential_integrity(
    conn: Connection,
    child_tbl: str,
    parent_tbl: str,
    child_col: str,
    parent_col: str,
) -> None:
    """Phase 2: No orphaned foreign keys in category tables."""
    count = conn.execute(
        text(
            f"SELECT count(*) FROM {child_tbl} c "
            f"LEFT JOIN {parent_tbl} p ON c.{child_col} = p.{parent_col} "
            f"WHERE p.{parent_col} IS NULL"
        )
    ).scalar()
    assert count == 0, (
        f"{count} rows in {child_tbl}.{child_col} without matching "
        f"{parent_tbl}.{parent_col}"
    )


@ pytest.mark.parametrize(
    "tbl,col",
    CATEGORY_NOT_NULL_COLS,
    ids=[f"{t}.{c}" for t, c in CATEGORY_NOT_NULL_COLS],
)
def test_category_not_null_critical_columns(
    conn: Connection, tbl: str, col: str
) -> None:
    """Phase 2: Critical columns in category_analytics have no NULLs."""
    count: int = conn.execute(
        text(f"SELECT count(*) FROM {tbl} WHERE {col} IS NULL")
    ).scalar() or 0
    assert count == 0, f"{tbl}.{col} has {count} NULL values"


def test_category_analytics_roi_range(conn: Connection) -> None:
    """Phase 2: ROI in category_analytics is within reasonable bounds.

    Valid range: -100% (-1.0) to +10000% (100.0).
    """
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM category_analytics "
            "WHERE roi IS NOT NULL AND (roi < -1.0 OR roi > 100.0)"
        )
    ).scalar() or 0
    assert count == 0, f"{count} rows have ROI outside [-1.0, 100.0]"


def test_category_analytics_win_rate_range(conn: Connection) -> None:
    """Phase 2: win_rate in category_analytics is within [0, 1]."""
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM category_analytics "
            "WHERE win_rate IS NOT NULL AND (win_rate < 0 OR win_rate > 1)"
        )
    ).scalar() or 0
    assert count == 0, f"{count} rows have win_rate outside [0, 1]"


def test_category_analytics_wallets_exist(conn: Connection) -> None:
    """Phase 2: All wallets in category_analytics exist in wallets table."""
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM category_analytics ca "
            "LEFT JOIN wallets w ON ca.wallet = w.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"{count} wallets in category_analytics not in wallets table"


def test_category_rankings_wallets_exist(conn: Connection) -> None:
    """Phase 2: All wallets in category_rankings exist in wallets table."""
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM category_rankings cr "
            "LEFT JOIN wallets w ON cr.wallet = w.wallet "
            "WHERE w.wallet IS NULL"
        )
    ).scalar() or 0
    assert count == 0, f"{count} wallets in category_rankings not in wallets table"
```

### 6.4 Integration Test Inventory

| # | Test Name | What it validates |
|---|-----------|-------------------|
| 1 | `test_category_table_row_counts[category_analytics ≥ 100]` | ≥ 100 rows |
| 2 | `test_category_table_row_counts[category_rankings ≥ 50]` | ≥ 50 rows |
| 3 | `test_category_referential_integrity[category_analytics.wallet → wallets.wallet]` | No orphan FKs |
| 4 | `test_category_referential_integrity[category_rankings.wallet → wallets.wallet]` | No orphan FKs |
| 5 | `test_category_not_null_critical_columns[category_analytics.wallet]` | wallet not null |
| 6 | `test_category_not_null_critical_columns[category_analytics.category]` | category not null |
| 7 | `test_category_not_null_critical_columns[category_analytics.snapshot_date]` | snapshot_date not null |
| 8 | `test_category_analytics_roi_range` | ROI ∈ [-1.0, 100.0] |
| 9 | `test_category_analytics_win_rate_range` | win_rate ∈ [0, 1] |
| 10 | `test_category_analytics_wallets_exist` | wallets exist in `wallets` |
| 11 | `test_category_rankings_wallets_exist` | wallets exist in `wallets` |

> **Note**: Due to parametrization, 8 test *functions* produce 11 test *cases* (3 for not-null, 2 for row counts, 2 for FKs, 4 standalone).

### 6.5 No Changes to Existing Tests

All existing 32 integration tests remain untouched. The new code is appended after line 268.

---

## 7. `app/tests/test_category_classifier.py` — 10 Classifier Unit Tests

### 7.1 Complete File Content

```python
"""Unit tests for the category classifier (infer_category function).

Pattern: pure functions, no database, no mocking.
Tests cover all 8 known categories plus unclassifiable and case insensitivity.
"""

import pytest

from app.models.enums import MarketCategory
from app.services.category_classifier import infer_category


# ═══════════════════════════════════════════════════════════════════════
# Positive tests — each known category
# ═══════════════════════════════════════════════════════════════════════

def test_classify_politics() -> None:
    """Questions about elections, candidates, and political offices."""
    inputs = [
        "Will Donald Trump win the 2024 election?",
        "Who will be the next US President?",
        "Will the Democratic party win the Senate in 2025?",
        "Will there be a government shutdown in 2024?",
        "Will Gavin Newsom run for president?",
    ]
    for question in inputs:
        result = infer_category(question)
        assert result == MarketCategory.POLITICS, (
            f"Expected POLITICS for: {question!r}, got {result}"
        )


def test_classify_crypto() -> None:
    """Questions about cryptocurrencies, tokens, and blockchain."""
    inputs = [
        "Will Bitcoin reach $100k by end of 2025?",
        "Will Ethereum 2.0 launch before July?",
        "Will Solana price exceed $200 this quarter?",
        "Will the SEC approve a Bitcoin ETF?",
        "Will Uniswap governance pass proposal 5?",
    ]
    for question in inputs:
        result = infer_category(question)
        assert result == MarketCategory.CRYPTO, (
            f"Expected CRYPTO for: {question!r}, got {result}"
        )


def test_classify_sports() -> None:
    """Questions about sports outcomes, teams, and leagues."""
    inputs = [
        "Will the Chiefs win the Super Bowl?",
        "Who will win the NBA Finals 2025?",
        "Will Novak Djokovic win Wimbledon?",
        "Will Manchester United finish top 4 this season?",
        "Will the Dodgers win the World Series?",
    ]
    for question in inputs:
        result = infer_category(question)
        assert result == MarketCategory.SPORTS, (
            f"Expected SPORTS for: {question!r}, got {result}"
        )


def test_classify_ai() -> None:
    """Questions about artificial intelligence and machine learning."""
    inputs = [
        "Will GPT-5 be released before 2026?",
        "Will OpenAI achieve AGI by 2030?",
        "Will AI-generated art win a major competition?",
        "Will a self-driving car service launch in NYC?",
        "Will Claude 4 outperform GPT-4 on benchmarks?",
    ]
    for question in inputs:
        result = infer_category(question)
        assert result == MarketCategory.AI, (
            f"Expected AI for: {question!r}, got {result}"
        )


def test_classify_geopolitics() -> None:
    """Questions about international relations and conflicts."""
    inputs = [
        "Will there be a ceasefire in Ukraine by June?",
        "Will North Korea launch another missile test?",
        "Will China sanction Taiwan before 2026?",
        "Will the US withdraw from NATO?",
        "Will Iran resume nuclear negotiations?",
    ]
    for question in inputs:
        result = infer_category(question)
        assert result == MarketCategory.GEOPOLITICS, (
            f"Expected GEOPOLITICS for: {question!r}, got {result}"
        )


def test_classify_economics() -> None:
    """Questions about economic indicators and policy."""
    inputs = [
        "Will the Fed cut rates in March?",
        "Will US inflation drop below 3%?",
        "Will the unemployment rate rise above 5%?",
        "Will GDP growth exceed 2% this quarter?",
        "Will the S&P 500 reach a new all-time high?",
    ]
    for question in inputs:
        result = infer_category(question)
        assert result == MarketCategory.ECONOMICS, (
            f"Expected ECONOMICS for: {question!r}, got {result}"
        )


def test_classify_technology() -> None:
    """Questions about tech products, companies, and innovation."""
    inputs = [
        "Will Apple release a VR headset?",
        "Will Tesla deliver 2 million vehicles this year?",
        "Will SpaceX land Starship on Mars?",
        "Will Amazon launch a satellite internet service?",
        "Will TSMC build a 1nm chip factory?",
    ]
    for question in inputs:
        result = infer_category(question)
        assert result == MarketCategory.TECHNOLOGY, (
            f"Expected TECHNOLOGY for: {question!r}, got {result}"
        )


def test_classify_entertainment() -> None:
    """Questions about movies, music, and media."""
    inputs = [
        "Will Oppenheimer win Best Picture?",
        "Will the new Star Wars movie break $1B box office?",
        "Will Taylor Swift's tour gross over $500M?",
        "Will Netflix gain 10 million subscribers this quarter?",
        "Will GTA 6 release before 2026?",
    ]
    for question in inputs:
        result = infer_category(question)
        assert result == MarketCategory.ENTERTAINMENT, (
            f"Expected ENTERTAINMENT for: {question!r}, got {result}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Negative / edge case tests
# ═══════════════════════════════════════════════════════════════════════

def test_classify_unclassifiable() -> None:
    """Questions that don't match any category return None."""
    inputs = [
        "Will it rain in Paris tomorrow?",
        "What is the meaning of life?",
        "Will the sun rise in the east?",
        "Will this prediction market platform succeed?",
        "Will a meteor hit Earth this year?",
    ]
    for question in inputs:
        result = infer_category(question)
        assert result is None, (
            f"Expected None for: {question!r}, got {result}"
        )


def test_classify_case_insensitive() -> None:
    """Category matching is case-insensitive."""
    test_cases = [
        # (input_question, expected_category)
        ("will donald trump win the 2024 election", MarketCategory.POLITICS),
        ("WILL BITCOIN REACH $100K", MarketCategory.CRYPTO),
        ("will the chiefs win the super bowl", MarketCategory.SPORTS),
        ("Will Gpt-5 Be Released Before 2026?", MarketCategory.AI),
        ("WILL THERE BE A CEASEFIRE IN UKRAINE", MarketCategory.GEOPOLITICS),
    ]
    for question, expected in test_cases:
        result = infer_category(question)
        assert result == expected, (
            f"Expected {expected} for case-insensitive: {question!r}, got {result}"
        )
```

### 7.2 Test Data Summary

Each positive test uses 5 representative questions per category (40 total inputs). The unclassifiable test uses 5 inputs. Case-insensitivity uses 5 cross-case variants. Total: 50 test calls across 10 test functions.

| Category | Example Input |
|----------|---------------|
| Politics | "Will Donald Trump win the 2024 election?" |
| Crypto | "Will Bitcoin reach $100k by end of 2025?" |
| Sports | "Will the Chiefs win the Super Bowl?" |
| AI | "Will GPT-5 be released before 2026?" |
| Geopolitics | "Will there be a ceasefire in Ukraine by June?" |
| Economics | "Will the Fed cut rates in March?" |
| Technology | "Will Apple release a VR headset?" |
| Entertainment | "Will Oppenheimer win Best Picture?" |
| Unclassifiable | "Will it rain in Paris tomorrow?" |
| Case-insensitive | "will donald trump win the 2024 election" → Politics |

---

## 8. Edge Cases Not Covered by Tests

The following edge cases are documented in the plan but intentionally excluded from the automated test suite because they require production data or multi-step environmental setup:

| Scenario | Why Not Tested |
|----------|----------------|
| Wallet has 0 trades in category | Handled by ETL pipeline — no row created |
| Wallet has < 30 trades → `is_specialist = False` | ETL logic, not testable via API mocks |
| Category has only 1 trader | Needs specific DB seed data |
| All ROI values are equal | Needs specific DB seed data |
| Market category changes between runs | Snapshot-based, needs multi-run setup |
| Empty categories (no traders at all) | No rows → not queryable |
| Wallet in multiple categories | Covered by test 5 (wallet_categories) |
| Migration forward + backward | Manual verification (see plan §6) |

---

## 9. How to Run

```bash
# Run ALL tests (Phase 1 + Phase 2)
python3 -m pytest app/tests/ -v

# Run only API tests (new + existing)
python3 -m pytest app/tests/test_api/ -v

# Run only the new category API tests
python3 -m pytest app/tests/test_api/test_category_endpoints.py -v

# Run only integration tests (new + existing)
python3 -m pytest app/tests/test_db_integrity.py -m integration -v

# Run only classifier tests
python3 -m pytest app/tests/test_category_classifier.py -v

# Run a single test
python3 -m pytest app/tests/test_category_classifier.py::test_classify_politics -v

# Run with coverage
python3 -m pytest app/tests/ -v --cov=app --cov-report=term-missing
```

---

## 10. Acceptance Checklist

- [ ] **`test_category_endpoints.py`** — all 8 tests pass with mocked DB
- [ ] **`test_category_classifier.py`** — all 10 tests pass with no DB
- [ ] **`test_db_integrity.py`** — all 11 parametrized category cases pass with real DB
- [ ] **No regressions** — all 41 existing Phase 1 tests still pass
- [ ] **Total 67 tests** — 17 API + 40 integration + 10 classifier
- [ ] **Response shapes** match Pydantic schema definitions
- [ ] **404 handling** works for invalid categories and missing wallets
- [ ] **ROI bounds** `[-1.0, 100.0]` enforced by integration tests
- [ ] **win_rate bounds** `[0, 1]` enforced by integration tests
- [ ] **Referential integrity** validated for both `category_analytics` and `category_rankings`
- [ ] **Classifier coverage** includes all 8 MarketCategory values plus unclassifiable and case-insensitive paths
