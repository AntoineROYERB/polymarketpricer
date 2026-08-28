from datetime import date, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, field_validator


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
    edge_score: float | None = None
    edge_consistency: float | None = None
    num_edge_trades: int | None = None

    model_config = {"from_attributes": True}


class LeaderboardResponse(BaseModel):
    data: list[LeaderboardEntry]
    limit: int
    offset: int


class PositionSummary(BaseModel):
    market_id: str
    question: str
    event_slug: str | None = None
    condition_id: str | None = None
    side: str | None = None
    status: str = "OPEN"
    shares: float
    avg_entry_price: float
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    total_pnl: float | None = None

    model_config = {"from_attributes": True}


class WalletAnalyticsData(BaseModel):
    total_pnl: float | None = None
    roi: float | None = None
    win_rate: float | None = None
    num_trades: int | None = None
    total_volume: float | None = None
    avg_position_size: float | None = None
    sharpe_ratio: float | None = None
    profit_factor: float | None = None
    max_drawdown: float | None = None
    avg_holding_duration: str | None = None
    consistency_score: float | None = None
    experience_score: float | None = None

    model_config = {"from_attributes": True}

    @field_validator("avg_holding_duration", mode="before")
    @classmethod
    def coerce_timedelta_to_str(cls, v: object) -> object:
        if isinstance(v, timedelta):
            return str(v)
        return v


class WalletEdgeSnapshot(BaseModel):
    wallet: str
    snapshot_date: date | None = None
    avg_edge: float
    median_edge: float | None = None
    edge_consistency: float | None = None
    edge_volatility: float | None = None
    edge_score: float | None = None
    num_edge_trades: int
    positive_edge_trades: int | None = None
    negative_edge_trades: int | None = None
    computed_at: datetime | None = None

    model_config = {"from_attributes": True}


class EdgeLeaderboardEntry(BaseModel):
    wallet: str
    edge_score: float
    avg_edge: float
    edge_consistency: float | None = None
    num_edge_trades: int
    rank: int


class EdgeLeaderboardResponse(BaseModel):
    data: list[EdgeLeaderboardEntry]
    limit: int
    offset: int


class WalletProfile(BaseModel):
    wallet: str
    main_wallet: str | None = None
    label: str | None = None
    is_tracked: bool = True
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    last_position_sync: datetime | None = None
    last_trade_sync: datetime | None = None
    analytics: WalletAnalyticsData | None = None
    current_positions: list[PositionSummary] = []
    rank: int | None = None
    categories: list["WalletCategorySummary"] = []
    edge_metrics: WalletEdgeSnapshot | None = None

    model_config = {"from_attributes": True}


class CategoryLeaderboardEntry(BaseModel):
    rank: int
    wallet: str
    wallet_score: float | None = None
    roi: float | None = None
    win_rate: float | None = None
    total_pnl: float | None = None
    num_trades: int = 0
    total_volume: float | None = None
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
    total_volume: float | None = None
    total_pnl: float | None = None
    roi: float | None = None
    win_rate: float | None = None
    profit_factor: float | None = None
    avg_position_size: float | None = None
    is_specialist: bool = False
    category_rank: int | None = None

    model_config = {"from_attributes": True}


class WalletCategoryResponse(BaseModel):
    wallet: str
    categories: list[WalletCategorySummary]


class CategoryDetailResponse(BaseModel):
    wallet: str
    category: str
    num_trades: int = 0
    total_volume: float | None = None
    total_cost_basis: float | None = None
    total_pnl: float | None = None
    total_realized_pnl: float | None = None
    total_unrealized_pnl: float | None = None
    roi: float | None = None
    win_rate: float | None = None
    num_resolved_positions: int = 0
    profit_factor: float | None = None
    avg_position_size: float | None = None
    avg_holding_duration: str | None = None
    is_specialist: bool = False
    category_rank: int | None = None

    model_config = {"from_attributes": True}


class CategoryItem(BaseModel):
    category: str
    label: str


class AlertItem(BaseModel):
    id: UUID
    wallet: str
    market_id: str
    market_question: str
    event_slug: str | None = None
    condition_id: str | None = None
    action: str
    price: float
    position_size: float
    wallet_score: float
    category: str
    detected_at: datetime
    notified_at: datetime | None = None

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    data: list[AlertItem]
    limit: int
    offset: int


class MarketSummary(BaseModel):
    id: str
    question: str
    category: str | None = None
    event_slug: str | None = None
    volume_usd: float | None = None
    liquidity_usd: float | None = None
    close_time: datetime | None = None
    created_at: datetime | None = None
    resolved_at: datetime | None = None
    winning_outcome: str | None = None

    model_config = {"from_attributes": True}


class MarketListResponse(BaseModel):
    data: list[MarketSummary]
    total: int = 0
    limit: int
    offset: int


class OutcomeResponse(BaseModel):
    id: str
    label: str
    price: float | None = None
    winner: bool | None = None

    model_config = {"from_attributes": True}


class ActiveTraderEntry(BaseModel):
    wallet: str
    side: str | None = None
    position_size: float | None = None
    price: float | None = None
    total_pnl: float | None = None


class MarketDetailResponse(BaseModel):
    id: str
    question: str
    category: str | None = None
    event_slug: str | None = None
    condition_id: str | None = None
    volume_usd: float | None = None
    liquidity_usd: float | None = None
    close_time: datetime | None = None
    created_at: datetime | None = None
    resolved_at: datetime | None = None
    winning_outcome: str | None = None

    model_config = {"from_attributes": True}
    outcomes: list[OutcomeResponse] = []
    buy_percent: float = 50.0
    active_traders: list[ActiveTraderEntry] = []




