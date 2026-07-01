# mypy: disable-error-code="assignment"

import re
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
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
from app.services.wallet_service import get_wallet_profile
from app.utils.category import validate_category_or_404

router = APIRouter()

_USER_ID = "default"  # placeholder until auth is implemented
_MAX_FOLLOWS = 500
_WALLET_RE = re.compile(r"^0x.+$")


def _validate_wallet(wallet: str) -> None:
    """Validate wallet address format."""
    if not _WALLET_RE.match(wallet):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid wallet address format: '{wallet}'. Expected 0x-prefixed 42-char hex address.",
        )


@router.get("/recommendations", response_model=FollowRecommendationResponse)
async def recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FollowRecommendationResponse:
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
) -> CategoryFollowLeaderboardResponse:
    """Top-N wallets to follow in a specific category."""
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
) -> WalletCategoryFollowScoresResponse:
    """Per-category follow scores for a specific wallet."""
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
    auto_copy: Optional[bool] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> FollowListResponse:
    """List wallets the user follows."""
    stmt = select(WalletFollow).where(
        WalletFollow.user_id == _USER_ID,
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
) -> FollowResponse:
    """Start following a wallet."""
    _validate_wallet(wallet)

    w = await db.execute(select(Wallet).where(Wallet.wallet == wallet))
    if w.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Max-follows limit
    count_result = await db.execute(
        select(func.count()).select_from(WalletFollow).where(
            WalletFollow.user_id == _USER_ID,
            WalletFollow.active.is_(True),
        )
    )
    current_count = count_result.scalar() or 0
    if current_count >= _MAX_FOLLOWS:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum of {_MAX_FOLLOWS} follows reached.",
        )

    existing = await db.execute(
        select(WalletFollow).where(
            WalletFollow.user_id == _USER_ID,
            WalletFollow.wallet == wallet,
        ).order_by(WalletFollow.followed_at.desc())
    )
    existing_row = existing.scalar_one_or_none()

    if existing_row and existing_row.active:
        raise HTTPException(status_code=409, detail="Already following this wallet")

    if existing_row and not existing_row.active:
        follow = existing_row
        follow.active = True
        follow.auto_copy_enabled = body.auto_copy_enabled or False
        follow.copy_mode = body.copy_mode
        follow.copy_value = body.copy_value
        follow.category_filter = body.category_filter
        follow.label = body.label
        follow.unfollowed_at = None
    else:
        follow = WalletFollow(
            user_id=_USER_ID,
            wallet=wallet,
            label=body.label,
            auto_copy_enabled=body.auto_copy_enabled or False,
            copy_mode=body.copy_mode,
            copy_value=body.copy_value,
            category_filter=body.category_filter,
        )
        db.add(follow)

    if body.auto_copy_enabled:
        portfolio = await db.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == _USER_ID)
        )
        if portfolio.scalar_one_or_none() is None:
            new_portfolio = PaperPortfolio(
                user_id=_USER_ID,
                name="Main",
                initial_balance=Decimal("10000"),
                current_balance=Decimal("10000"),
                total_realized_pnl=Decimal("0"),
                total_unrealized_pnl=Decimal("0"),
                total_pnl=Decimal("0"),
                total_trades=0,
                total_volume=Decimal("0"),
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
) -> FollowResponse:
    """Update follow configuration."""
    _validate_wallet(wallet)
    result = await db.execute(
        select(WalletFollow).where(
            WalletFollow.user_id == _USER_ID,
            WalletFollow.wallet == wallet,
            WalletFollow.active.is_(True),
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
) -> None:
    """Unfollow a wallet (soft delete)."""
    _validate_wallet(wallet)
    result = await db.execute(
        select(WalletFollow).where(
            WalletFollow.user_id == _USER_ID,
            WalletFollow.wallet == wallet,
            WalletFollow.active.is_(True),
        )
    )
    follow = result.scalar_one_or_none()
    if follow is None:
        raise HTTPException(status_code=404, detail="Follow not found")

    follow.active = False
    follow.unfollowed_at = func.now()
    await db.commit()
