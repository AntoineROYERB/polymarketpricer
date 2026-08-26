from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from typing import Literal

from app.utils.category import get_valid_categories


class FollowCreate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
    auto_copy_enabled: bool = False
    copy_mode: Optional[Literal["proportional", "fixed"]] = None
    copy_value: float = Field(default=0.05, ge=0)
    category_filter: Optional[list[str]] = None

    model_config = {"from_attributes": True}

    @field_validator("category_filter")
    @classmethod
    def validate_category_filter(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        valid = set(get_valid_categories())
        for cat in v:
            if cat.lower() not in valid:
                raise ValueError(f"Invalid category '{cat}'. Valid: {sorted(valid)}")
        return [cat.lower() for cat in v]


class FollowUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
    auto_copy_enabled: Optional[bool] = None
    copy_mode: Optional[Literal["proportional", "fixed"]] = None
    copy_value: Optional[float] = Field(default=None, ge=0)
    category_filter: Optional[list[str]] = None
    active: Optional[bool] = None

    @field_validator("category_filter")
    @classmethod
    def validate_category_filter(cls, v: Optional[list[str]]) -> Optional[list[str]]:
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
    label: Optional[str] = None
    active: bool
    auto_copy_enabled: bool
    copy_mode: Optional[str] = None
    copy_value: float
    category_filter: Optional[list[str]] = None
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
    id: Optional[UUID] = None
    name: str = "Main"
    initial_balance: float = 10000.0
    current_balance: float = 10000.0
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    total_roi: Optional[float] = None
    total_trades: int = 0
    total_volume: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaperPositionResponse(BaseModel):
    id: UUID
    market_id: str
    event_slug: Optional[str] = None
    condition_id: Optional[str] = None
    outcome: str
    side: str
    status: str
    shares: float
    avg_entry_price: float
    current_price: Optional[float] = None
    cost_basis: float
    realized_pnl: float
    unrealized_pnl: Optional[float] = None
    followed_wallet: str
    opened_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaperPositionListResponse(BaseModel):
    data: list[PaperPositionResponse]
    total: int


class PaperTradeResponse(BaseModel):
    id: UUID
    market_id: str
    event_slug: Optional[str] = None
    condition_id: Optional[str] = None
    outcome: str
    side: str
    price: float
    shares: float
    amount_usd: float
    followed_wallet: str
    copy_mode: Optional[str] = None
    copy_value_used: Optional[float] = None
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
    roi_percentile: Optional[float] = None
    win_rate: Optional[float] = None
    is_specialist: bool = False
    volume_percentile: Optional[float] = None
    recency_days: Optional[int] = None
    reasons: list[str] = []

    model_config = {"from_attributes": True}


class WalletCategoryFollowScoresResponse(BaseModel):
    wallet: str
    global_follow_score: Optional[float] = None
    category_scores: list[CategoryFollowScoreItem]


class CategoryFollowLeaderboardEntry(BaseModel):
    wallet: str
    follow_score: float
    recommendation: str
    roi_percentile: Optional[float] = None
    win_rate: Optional[float] = None
    is_specialist: bool = False
    reasons: list[str] = []


class CategoryFollowLeaderboardResponse(BaseModel):
    category: str
    data: list[CategoryFollowLeaderboardEntry]
    limit: int
    offset: int
