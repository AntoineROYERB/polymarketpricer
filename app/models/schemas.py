from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from typing import Literal

from app.utils.category import get_valid_categories


class LeaderboardEntry(BaseModel):
    rank: int
    wallet: str
    score: float
    roi: float
    win_rate: float
    total_pnl: float
    num_trades: int
    consistency_score: float
    experience_score: float
    edge_score: Optional[float] = None
    edge_consistency: Optional[float] = None
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
    shares: float
    avg_entry_price: float
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    total_pnl: Optional[float] = None

    model_config = {"from_attributes": True}


class WalletAnalyticsData(BaseModel):
    total_pnl: Optional[float] = None
    roi: Optional[float] = None
    win_rate: Optional[float] = None
    num_trades: Optional[int] = None
    total_volume: Optional[float] = None
    avg_position_size: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    max_drawdown: Optional[float] = None
    avg_holding_duration: Optional[str] = None
    consistency_score: Optional[float] = None
    experience_score: Optional[float] = None

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
    avg_edge: float
    median_edge: Optional[float] = None
    edge_consistency: Optional[float] = None
    edge_volatility: Optional[float] = None
    edge_score: Optional[float] = None
    num_edge_trades: int
    positive_edge_trades: Optional[int] = None
    negative_edge_trades: Optional[int] = None
    computed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EdgeLeaderboardEntry(BaseModel):
    wallet: str
    edge_score: float
    avg_edge: float
    edge_consistency: Optional[float] = None
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
    wallet_score: Optional[float] = None
    roi: Optional[float] = None
    win_rate: Optional[float] = None
    total_pnl: Optional[float] = None
    num_trades: int = 0
    total_volume: Optional[float] = None
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
    total_volume: Optional[float] = None
    total_pnl: Optional[float] = None
    roi: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    avg_position_size: Optional[float] = None
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
    total_volume: Optional[float] = None
    total_cost_basis: Optional[float] = None
    total_pnl: Optional[float] = None
    total_realized_pnl: Optional[float] = None
    total_unrealized_pnl: Optional[float] = None
    roi: Optional[float] = None
    win_rate: Optional[float] = None
    num_resolved_positions: int = 0
    profit_factor: Optional[float] = None
    avg_position_size: Optional[float] = None
    avg_holding_duration: Optional[str] = None
    is_specialist: bool = False
    category_rank: Optional[int] = None

    model_config = {"from_attributes": True}


class CategoryItem(BaseModel):
    category: str
    label: str


class AlertItem(BaseModel):
    id: UUID
    wallet: str
    market_id: str
    market_question: str
    action: str
    price: float
    position_size: float
    wallet_score: float
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
    volume_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    close_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    winning_outcome: Optional[str] = None

    model_config = {"from_attributes": True}


class MarketListResponse(BaseModel):
    data: list[MarketSummary]
    limit: int
    offset: int


class OutcomeResponse(BaseModel):
    id: str
    label: str
    price: Optional[float] = None
    winner: Optional[bool] = None

    model_config = {"from_attributes": True}


class ActiveTraderEntry(BaseModel):
    wallet: str
    side: Optional[str] = None
    position_size: Optional[float] = None
    price: Optional[float] = None
    total_pnl: Optional[float] = None


class MarketDetailResponse(BaseModel):
    id: str
    question: str
    category: Optional[str] = None
    event_slug: Optional[str] = None
    condition_id: Optional[str] = None
    volume_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    close_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    winning_outcome: Optional[str] = None

    model_config = {"from_attributes": True}
    outcomes: list[OutcomeResponse] = []
    buy_percent: float = 50.0
    active_traders: list[ActiveTraderEntry] = []


# ── Phase 5: Follow ─────────────────────────────────────────────────

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


# ── Phase 5: Paper Trading ──────────────────────────────────────────

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


# ── Phase 5: Per-Category Follow Scores ─────────────────────────────

class CategoryFollowScoreItem(BaseModel):
    category: str
    follow_score: float
    recommendation: str  # FOLLOW / WATCH / IGNORE
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

