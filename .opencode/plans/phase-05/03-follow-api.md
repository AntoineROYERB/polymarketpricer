# Phase 5 — Follow & Paper Trading — Wallet Follow API

> **Goal**: Expose CRUD endpoints for wallet following and follow recommendations.
> **AI Agent Instructions**: Create `app/api/v1/follow.py` with all follow-related endpoints, register in `app/api/router.py`.

---

## Endpoints

### `GET /api/v1/follow/recommendations`

Returns wallets ranked by `follow_score` descending.

**Query Parameters:**

| Param | Type | Default | Valid Range | Description |
|-------|------|---------|-------------|-------------|
| `limit` | int | 20 | 1–100 | Max results |
| `offset` | int | 0 | ≥ 0 | Pagination offset |

**Response `200 OK`:**
```json
{
  "data": [
    {
      "wallet": "0x1234...abcd",
      "follow_score": 0.92,
      "reasons": [
        "Edge score: 0.95",
        "Specialist in Politics, Crypto",
        "Consistency: 0.78"
      ]
    }
  ],
  "limit": 20,
  "offset": 0
}
```

**Error Responses:** 422 for invalid params.

---

### `GET /api/v1/follow`

List all wallets the user is currently following.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `active` | bool | `true` | Filter by active/inactive |
| `auto_copy` | bool | — | Filter by auto_copy_enabled |

**Response `200 OK`:**
```json
{
  "data": [
    {
      "id": "uuid",
      "wallet": "0x1234...abcd",
      "label": "Politics whale",
      "active": true,
      "auto_copy_enabled": true,
      "copy_mode": "proportional",
      "copy_value": 0.05,
      "category_filter": ["Politics", "Crypto"],
      "followed_at": "2026-06-29T12:00:00+00:00",
      "updated_at": "2026-06-29T12:00:00+00:00"
    }
  ],
  "total": 1
}
```

---

### `POST /api/v1/follow/{wallet}`

Start following a wallet with optional configuration.

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `wallet` | str | Ethereum address (0x-prefixed) |

**Request Body:**
```json
{
  "label": "Politics whale",
  "auto_copy_enabled": true,
  "copy_mode": "proportional",
  "copy_value": 0.05,
  "category_filter": ["Politics", "Crypto"]
}
```

All fields optional:
- `label` — custom label
- `auto_copy_enabled` — default `false`
- `copy_mode` — `"proportional"` or `"fixed"` (required if auto_copy=true)
- `copy_value` — default `0.05` (5% or $X)
- `category_filter` — array of categories, null = all

**Response `201 Created`:**
```json
{
  "id": "uuid",
  "wallet": "0x1234...abcd",
  "label": "Politics whale",
  "active": true,
  "auto_copy_enabled": true,
  "copy_mode": "proportional",
  "copy_value": 0.05,
  "category_filter": ["Politics", "Crypto"],
  "followed_at": "2026-06-29T12:00:00+00:00",
  "updated_at": "2026-06-29T12:00:00+00:00"
}
```

**Error Responses:**

| Status | Body | When |
|--------|------|------|
| 404 | `{"detail": "Wallet not found"}` | Unknown wallet |
| 409 | `{"detail": "Already following this wallet"}` | Duplicate follow |
| 422 | `{"detail": [...]}` | Invalid params (e.g. bad copy_mode) |

---

### `PATCH /api/v1/follow/{wallet}`

Update follow configuration.

**Path Parameters:** Same as POST.

**Request Body:** Same fields as POST, all optional (partial update).

**Response `200 OK`:** Updated `FollowResponse`.

---

### `DELETE /api/v1/follow/{wallet}`

Unfollow a wallet (soft delete — sets `active = false`, `unfollowed_at = now()`).

**Response `204 No Content`.**

---

---

### `GET /api/v1/follow/recommendations/by-category/{category}`

Top wallets to follow in a specific category, ranked by per-category `follow_score` descending.

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `category` | str | Category name (e.g. `politics`, `crypto`) |

**Query Parameters:**

| Param | Type | Default | Valid Range | Description |
|-------|------|---------|-------------|-------------|
| `limit` | int | 20 | 1–100 | Max results |
| `offset` | int | 0 | ≥ 0 | Pagination offset |

**Response `200 OK`:**
```json
{
  "category": "politics",
  "data": [
    {
      "wallet": "0x1234...abcd",
      "follow_score": 0.92,
      "recommendation": "FOLLOW",
      "roi_percentile": 0.97,
      "win_rate": 0.78,
      "is_specialist": true,
      "reasons": [
        "Top 3% ROI in politics",
        "Politics specialist (120 trades)",
        "Positive global edge (0.88)"
      ]
    }
  ],
  "limit": 20,
  "offset": 0
}
```

**Error Responses:** 404 for invalid category, 422 for invalid params.

---

### `GET /api/v1/follow/recommendations/{wallet}/by-category`

All per-category follow scores for a specific wallet.

**Path Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `wallet` | str | Ethereum address (0x-prefixed) |

**Response `200 OK`:**
```json
{
  "wallet": "0x1234...abcd",
  "global_follow_score": 0.85,
  "category_scores": [
    {
      "category": "politics",
      "follow_score": 0.92,
      "recommendation": "FOLLOW",
      "roi_percentile": 0.97,
      "win_rate": 0.78,
      "is_specialist": true,
      "reasons": ["Top 3% ROI in politics"]
    },
    {
      "category": "crypto",
      "follow_score": 0.45,
      "recommendation": "WATCH",
      "roi_percentile": 0.55,
      "win_rate": 0.52,
      "is_specialist": false,
      "reasons": ["Only 8 trades — limited history"]
    },
    {
      "category": "sports",
      "follow_score": 0.12,
      "recommendation": "IGNORE",
      "roi_percentile": 0.15,
      "win_rate": 0.38,
      "is_specialist": false,
      "reasons": ["Win rate below 40%"]
    }
  ]
}
```

**Error Responses:** 404 for unknown wallet.

---

## Router Implementation

```python
# app/api/v1/follow.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.db.models import Wallet, WalletFollow, PaperPortfolio
from app.models.schemas import (
    FollowCreate, FollowUpdate, FollowResponse, FollowListResponse,
    FollowRecommendation, FollowRecommendationResponse,
    CategoryFollowLeaderboardEntry, CategoryFollowLeaderboardResponse,
    CategoryFollowScoreItem, WalletCategoryFollowScoresResponse,
)
from app.services.follow_scoring import (
    get_follow_recommendations,
    get_category_follow_leaderboard,
    get_wallet_category_scores,
)

router = APIRouter()


@router.get("/recommendations", response_model=FollowRecommendationResponse)
async def recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Top-N wallets recommended to follow (global follow_score)."""
    recs = await get_follow_recommendations(db, limit, offset)
    data = [
        FollowRecommendation(
            wallet=r["wallet"],
            follow_score=r["follow_score"],
            reasons=r["reasons"],
        )
        for r in recs
    ]
    return FollowRecommendationResponse(data=data, limit=limit, offset=offset)


@router.get(
    "/recommendations/by-category/{category}",
    response_model=CategoryFollowLeaderboardResponse,
)
async def recommendations_by_category(
    category: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Top-N wallets to follow in a specific category."""
    from app.utils.category import validate_category_or_404
    norm_category = validate_category_or_404(category)

    recs = await get_category_follow_leaderboard(db, norm_category, limit, offset)
    data = [
        CategoryFollowLeaderboardEntry(
            wallet=r["wallet"],
            follow_score=r["follow_score"],
            recommendation=r["recommendation"],
            roi_percentile=r.get("roi_percentile"),
            win_rate=r.get("win_rate"),
            is_specialist=r.get("is_specialist", False),
            reasons=r.get("reasons", []),
        )
        for r in recs
    ]
    return CategoryFollowLeaderboardResponse(
        category=category.lower(), data=data, limit=limit, offset=offset
    )


@router.get(
    "/recommendations/{wallet}/by-category",
    response_model=WalletCategoryFollowScoresResponse,
)
async def wallet_recommendations_by_category(
    wallet: str,
    db: AsyncSession = Depends(get_db),
):
    """Per-category follow scores for a specific wallet."""
    from app.services.wallet_service import get_wallet_profile
    w = await get_wallet_profile(db, wallet)
    if w is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    scores = await get_wallet_category_scores(db, wallet)
    global_score = None
    if scores:
        global_score = scores[0].get("global_follow_score")

    category_items = [
        CategoryFollowScoreItem(
            category=s["category"],
            follow_score=s["follow_score"],
            recommendation=s["recommendation"],
            roi_percentile=s.get("roi_percentile"),
            win_rate=s.get("win_rate"),
            is_specialist=s.get("is_specialist", False),
            volume_percentile=s.get("volume_percentile"),
            recency_days=s.get("recency_days"),
            reasons=s.get("reasons", []),
        )
        for s in scores
    ]

    return WalletCategoryFollowScoresResponse(
        wallet=wallet,
        global_follow_score=global_score,
        category_scores=category_items,
    )


@router.get("", response_model=FollowListResponse)
async def list_follows(
    active: bool = Query(default=True),
    auto_copy: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """List wallets the user follows."""
    stmt = select(WalletFollow).where(
        WalletFollow.user_id == "default",
        WalletFollow.active == active,
    )
    if auto_copy is not None:
        stmt = stmt.where(WalletFollow.auto_copy_enabled == auto_copy)
    stmt = stmt.order_by(WalletFollow.followed_at.desc())

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return FollowListResponse(
        data=[FollowResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("/{wallet}", status_code=status.HTTP_201_CREATED, response_model=FollowResponse)
async def follow_wallet(
    wallet: str,
    body: FollowCreate,
    db: AsyncSession = Depends(get_db),
):
    """Start following a wallet."""
    # Verify wallet exists
    w = await db.execute(select(Wallet).where(Wallet.wallet == wallet))
    if w.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Check duplicate
    existing = await db.execute(
        select(WalletFollow).where(
            WalletFollow.user_id == "default",
            WalletFollow.wallet == wallet,
            WalletFollow.active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already following this wallet")

    # Create follow
    follow = WalletFollow(
        user_id="default",
        wallet=wallet,
        label=body.label,
        auto_copy_enabled=body.auto_copy_enabled or False,
        copy_mode=body.copy_mode,
        copy_value=body.copy_value,
        category_filter=body.category_filter,
    )
    db.add(follow)

    # Auto-create paper portfolio if first follow with auto_copy
    if body.auto_copy_enabled:
        portfolio = await db.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == "default")
        )
        if portfolio.scalar_one_or_none() is None:
            new_portfolio = PaperPortfolio(
                user_id="default",
                initial_balance=Decimal("10000"),
                current_balance=Decimal("10000"),
            )
            db.add(new_portfolio)

    await db.commit()
    await db.refresh(follow)
    return FollowResponse.model_validate(follow)


@router.patch("/{wallet}", response_model=FollowResponse)
async def update_follow(
    wallet: str,
    body: FollowUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update follow configuration."""
    result = await db.execute(
        select(WalletFollow).where(
            WalletFollow.user_id == "default",
            WalletFollow.wallet == wallet,
            WalletFollow.active == True,
        )
    )
    follow = result.scalar_one_or_none()
    if follow is None:
        raise HTTPException(status_code=404, detail="Follow not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(follow, key, value)
    follow.updated_at = func.now()

    await db.commit()
    await db.refresh(follow)
    return FollowResponse.model_validate(follow)


@router.delete("/{wallet}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_wallet(
    wallet: str,
    db: AsyncSession = Depends(get_db),
):
    """Unfollow a wallet (soft delete)."""
    result = await db.execute(
        select(WalletFollow).where(
            WalletFollow.user_id == "default",
            WalletFollow.wallet == wallet,
            WalletFollow.active == True,
        )
    )
    follow = result.scalar_one_or_none()
    if follow is None:
        raise HTTPException(status_code=404, detail="Follow not found")

    follow.active = False
    follow.unfollowed_at = func.now()
    await db.commit()
```

---

## Router Registration

Edit `app/api/router.py`:

```python
from app.api.v1.follow import router as follow_router

api_router.include_router(follow_router, prefix="/follow", tags=["follow"])
```

---

## Files to Create / Modify

| Action | Path |
|--------|------|
| CREATE | `app/api/v1/follow.py` |
| EDIT | `app/api/router.py` — register follow router |
| EDIT | `app/services/follow_scoring.py` — add `get_category_follow_leaderboard`, `get_wallet_category_scores` |

---

## Verification

```bash
# Get recommendations by category
curl "http://localhost:8000/api/v1/follow/recommendations/by-category/politics?limit=5"

# Get wallet per-category scores
curl "http://localhost:8000/api/v1/follow/recommendations/0x1234...abcd/by-category"

# 404 for invalid category
curl "http://localhost:8000/api/v1/follow/recommendations/by-category/invalid"
```

---

## Verification

```bash
# Get recommendations
curl "http://localhost:8000/api/v1/follow/recommendations?limit=5"

# Follow a wallet
curl -X POST "http://localhost:8000/api/v1/follow/0x1234...abcd" \
  -H "Content-Type: application/json" \
  -d '{"label": "Test", "auto_copy_enabled": true, "copy_mode": "proportional", "copy_value": 0.1}'

# List follows
curl "http://localhost:8000/api/v1/follow"

# Update follow
curl -X PATCH "http://localhost:8000/api/v1/follow/0x1234...abcd" \
  -H "Content-Type: application/json" \
  -d '{"auto_copy_enabled": false}'

# Unfollow
curl -X DELETE "http://localhost:8000/api/v1/follow/0x1234...abcd"

# 404 for unknown wallet
curl -X POST "http://localhost:8000/api/v1/follow/0xdeadbeef"
```
