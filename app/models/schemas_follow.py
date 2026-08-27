from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.utils.category import get_valid_categories


class FollowCreate(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    auto_copy_enabled: bool = False
    copy_mode: Literal["proportional", "fixed"] | None = None
    copy_value: float = Field(default=0.05, ge=0)
    category_filter: list[str] | None = None

    model_config = {"from_attributes": True}

    @field_validator("category_filter")
    @classmethod
    def validate_category_filter(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        valid = set(get_valid_categories())
        for cat in v:
            if cat.lower() not in valid:
                raise ValueError(f"Invalid category '{cat}'. Valid: {sorted(valid)}")
        return [cat.lower() for cat in v]


class FollowUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    auto_copy_enabled: bool | None = None
    copy_mode: Literal["proportional", "fixed"] | None = None
    copy_value: float | None = Field(default=None, ge=0)
    category_filter: list[str] | None = None
    active: bool | None = None

    @field_validator("category_filter")
    @classmethod
    def validate_category_filter(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        valid = set(get_valid_categories())
        for cat in v:
            if cat.lower() not in valid:
                raise ValueError(f"Invalid category '{cat}'. Valid: {sorted(valid)}")
        return [cat.lower() for cat in v]


class FollowResponse(BaseModel):
    id: UUID
    wallet: str
    label: str | None = None
    active: bool
    auto_copy_enabled: bool
    copy_mode: str | None = None
    copy_value: float
    category_filter: list[str] | None = None
    followed_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FollowListResponse(BaseModel):
    data: list[FollowResponse]
    total: int


class FollowRecommendation(BaseModel):
    wallet: str
    follow_score: float
    reasons: list[str]


class FollowRecommendationResponse(BaseModel):
    data: list[FollowRecommendation]
    limit: int
    offset: int


class PortfolioResponse(BaseModel):
    id: UUID | None = None
    name: str = "Main"
    initial_balance: float = 10000.0
    current_balance: float = 10000.0
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    total_roi: float | None = None
    total_trades: int = 0
    total_volume: float = 0.0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaperPositionResponse(BaseModel):
    id: UUID
    market_id: str
    event_slug: str | None = None
    condition_id: str | None = None
    outcome: str
    side: str
    status: str
    shares: float
    avg_entry_price: float
    current_price: float | None = None
    cost_basis: float
    realized_pnl: float
    unrealized_pnl: float | None = None
    followed_wallet: str
    opened_at: datetime
    closed_at: datetime | None = None

    model_config = {"from_attributes": True}


class PaperPositionListResponse(BaseModel):
    data: list[PaperPositionResponse]
    total: int


class PaperTradeResponse(BaseModel):
    id: UUID
    market_id: str
    event_slug: str | None = None
    condition_id: str | None = None
    outcome: str
    side: str
    price: float
    shares: float
    amount_usd: float
    followed_wallet: str
    copy_mode: str | None = None
    copy_value_used: float | None = None
    executed_at: datetime

    model_config = {"from_attributes": True}


class PaperTradeListResponse(BaseModel):
    data: list[PaperTradeResponse]
    limit: int
    offset: int
    total: int


class PortfolioResetRequest(BaseModel):
    initial_balance: float = Field(default=10000.0, gt=0)


class PortfolioResetResponse(BaseModel):
    portfolio: PortfolioResponse
    message: str


class CategoryFollowScoreItem(BaseModel):
    category: str
    follow_score: float
    recommendation: str
    roi_percentile: float | None = None
    win_rate: float | None = None
    is_specialist: bool = False
    volume_percentile: float | None = None
    recency_days: int | None = None
    reasons: list[str] = []

    model_config = {"from_attributes": True}


class WalletCategoryFollowScoresResponse(BaseModel):
    wallet: str
    global_follow_score: float | None = None
    category_scores: list[CategoryFollowScoreItem]


class CategoryFollowLeaderboardEntry(BaseModel):
    wallet: str
    follow_score: float
    recommendation: str
    roi_percentile: float | None = None
    win_rate: float | None = None
    is_specialist: bool = False
    reasons: list[str] = []


class CategoryFollowLeaderboardResponse(BaseModel):
    category: str
    data: list[CategoryFollowLeaderboardEntry]
    limit: int
    offset: int
