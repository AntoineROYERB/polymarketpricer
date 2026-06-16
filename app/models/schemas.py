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
    shares: Decimal
    avg_entry_price: Decimal
    unrealized_pnl: Decimal

    model_config = {"from_attributes": True}


class WalletAnalyticsData(BaseModel):
    total_pnl: Decimal
    roi: Decimal
    win_rate: Decimal
    num_trades: int
    avg_position_size: Decimal
    risk_adj_return: Optional[Decimal] = None
    avg_holding_duration: Optional[str] = None

    model_config = {"from_attributes": True}


class WalletProfile(BaseModel):
    wallet: str
    main_wallet: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    analytics: Optional[WalletAnalyticsData] = None
    current_positions: list[PositionSummary] = []
    rank: Optional[int] = None

    model_config = {"from_attributes": True}


class MarketSummary(BaseModel):
    id: str
    question: str
    category: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    outcome: Optional[str] = None

    model_config = {"from_attributes": True}


class MarketListResponse(BaseModel):
    data: list[MarketSummary]
    limit: int
    offset: int
