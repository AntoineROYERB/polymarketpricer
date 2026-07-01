from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from typing import Literal

from app.utils.category import get_valid_categories


class LeaderboardEntry(BaseModel):
    rank: int
    wallet: str
    score: Decimal
    roi: Decimal
    win_rate: Decimal
    total_pnl: Decimal
    num_trades: int
    consistency_score: Decimal
    experience_score: Decimal
    edge_score: Optional[Decimal] = None
    edge_consistency: Optional[Decimal] = None
    num_edge_trades: Optional[int] = None

    model_config = {"from_attributes": True}


class LeaderboardResponse(BaseModel):
    data: list[LeaderboardEntry]
    limit: int
    offset: int


class PositionSummary(BaseModel):
    market_id: str
    question: str
    side: Optional[str] = None
    status: str = "OPEN"
    shares: Decimal
    avg_entry_price: Decimal
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    realized_pnl: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    total_pnl: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class WalletAnalyticsData(BaseModel):
    total_pnl: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    num_trades: Optional[int] = None
    total_volume: Optional[Decimal] = None
    avg_position_size: Optional[Decimal] = None
    sharpe_ratio: Optional[Decimal] = None
    profit_factor: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None
    avg_holding_duration: Optional[str] = None
    consistency_score: Optional[Decimal] = None
    experience_score: Optional[Decimal] = None

    model_config = {"from_attributes": True}

    @field_validator("avg_holding_duration", mode="before")
    @classmethod
    def coerce_timedelta_to_str(cls, v: object) -> object:
        if isinstance(v, timedelta):
            return str(v)
        return v


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
    categories: list["WalletCategorySummary"] = []
    edge_metrics: Optional[WalletEdgeSnapshot] = None

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}


class CategoryItem(BaseModel):
    category: str
    label: str


class AlertItem(BaseModel):
    id: str
    wallet: str
    market_id: str
    market_question: str
    action: str
    price: Decimal
    position_size: Decimal
    wallet_score: Decimal
    category: str
    detected_at: datetime
    notified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    data: list[AlertItem]
    limit: int
    offset: int


class MarketSummary(BaseModel):
    id: str
    question: str
    category: Optional[str] = None
    event_slug: Optional[str] = None
    volume_usd: Optional[Decimal] = None
    liquidity_usd: Optional[Decimal] = None
    close_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    winning_outcome: Optional[str] = None

    model_config = {"from_attributes": True}


class MarketListResponse(BaseModel):
    data: list[MarketSummary]
    limit: int
    offset: int


# ── Phase 5: Follow ─────────────────────────────────────────────────

class FollowCreate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
    auto_copy_enabled: bool = False
    copy_mode: Optional[Literal["proportional", "fixed"]] = None
    copy_value: Decimal = Field(default=Decimal("0.05"), ge=0)
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
    copy_value: Optional[Decimal] = Field(default=None, ge=0)
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
    copy_value: Decimal
    category_filter: Optional[list[str]] = None
    followed_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FollowListResponse(BaseModel):
    data: list[FollowResponse]
    total: int


class FollowRecommendation(BaseModel):
    wallet: str
    follow_score: Decimal
    reasons: list[str]


class FollowRecommendationResponse(BaseModel):
    data: list[FollowRecommendation]
    limit: int
    offset: int


# ── Phase 5: Paper Trading ──────────────────────────────────────────

class PortfolioResponse(BaseModel):
    id: Optional[UUID] = None
    name: str = "Main"
    initial_balance: Decimal = Decimal("10000")
    current_balance: Decimal = Decimal("10000")
    total_realized_pnl: Decimal = Decimal("0")
    total_unrealized_pnl: Decimal = Decimal("0")
    total_pnl: Decimal = Decimal("0")
    total_roi: Optional[Decimal] = None
    total_trades: int = 0
    total_volume: Decimal = Decimal("0")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaperPositionResponse(BaseModel):
    id: UUID
    market_id: str
    outcome: str
    side: str
    status: str
    shares: Decimal
    avg_entry_price: Decimal
    current_price: Optional[Decimal] = None
    cost_basis: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Optional[Decimal] = None
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
    outcome: str
    side: str
    price: Decimal
    shares: Decimal
    amount_usd: Decimal
    followed_wallet: str
    copy_mode: Optional[str] = None
    copy_value_used: Optional[Decimal] = None
    executed_at: datetime

    model_config = {"from_attributes": True}


class PaperTradeListResponse(BaseModel):
    data: list[PaperTradeResponse]
    limit: int
    offset: int
    total: int


class PortfolioResetRequest(BaseModel):
    initial_balance: Decimal = Field(default=Decimal("10000"), gt=0)


class PortfolioResetResponse(BaseModel):
    portfolio: PortfolioResponse
    message: str


# ── Phase 5: Per-Category Follow Scores ─────────────────────────────

class CategoryFollowScoreItem(BaseModel):
    category: str
    follow_score: Decimal
    recommendation: str  # FOLLOW / WATCH / IGNORE
    roi_percentile: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    is_specialist: bool = False
    volume_percentile: Optional[Decimal] = None
    recency_days: Optional[int] = None
    reasons: list[str] = []

    model_config = {"from_attributes": True}


class WalletCategoryFollowScoresResponse(BaseModel):
    wallet: str
    global_follow_score: Optional[Decimal] = None
    category_scores: list[CategoryFollowScoreItem]


class CategoryFollowLeaderboardEntry(BaseModel):
    wallet: str
    follow_score: Decimal
    recommendation: str
    roi_percentile: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    is_specialist: bool = False
    reasons: list[str] = []


class CategoryFollowLeaderboardResponse(BaseModel):
    category: str
    data: list[CategoryFollowLeaderboardEntry]
    limit: int
    offset: int

