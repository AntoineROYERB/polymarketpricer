from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


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
    total_pnl: Decimal
    roi: Decimal
    win_rate: Decimal
    num_trades: int
    total_volume: Optional[Decimal] = None
    avg_position_size: Decimal
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

    model_config = {"from_attributes": True}


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
