from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class AlertAction(str, Enum):
    NEW_POSITION = "NEW_POSITION"
    POSITION_INCREASE = "POSITION_INCREASE"
    POSITION_DECREASE = "POSITION_DECREASE"
    FULL_EXIT = "FULL_EXIT"


class AlertItem(BaseModel):
    id: str
    wallet: str
    market_id: str
    market_question: str
    action: AlertAction
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


class CategoryAnalyticsData(BaseModel):
    category: str
    num_trades: Optional[int] = None
    total_volume: Optional[Decimal] = None
    total_cost_basis: Optional[Decimal] = None
    total_pnl: Optional[Decimal] = None
    total_realized_pnl: Optional[Decimal] = None
    total_unrealized_pnl: Optional[Decimal] = None
    roi: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    num_resolved_positions: Optional[int] = None
    profit_factor: Optional[Decimal] = None
    avg_position_size: Optional[Decimal] = None
    avg_holding_duration: Optional[str] = None
    is_specialist: bool = False
    category_rank: Optional[int] = None

    model_config = {"from_attributes": True}



