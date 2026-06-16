from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Interval,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from app.models.enums import PositionStatus, TradeSide, TradeType


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    slug = Column(Text, nullable=True)
    category = Column(Text, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    closed = Column(Boolean, nullable=False, default=False)

    markets = relationship("Market", back_populates="event")


class Market(Base):
    __tablename__ = "markets"

    id = Column(Text, primary_key=True)
    question = Column(Text, nullable=False)
    category = Column(Text, nullable=True)
    event_id = Column(Text, ForeignKey("events.id"), nullable=True)
    event_slug = Column(Text, nullable=True)
    volume_usd = Column(Numeric(28, 2), nullable=True)
    liquidity_usd = Column(Numeric(28, 2), nullable=True)
    close_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    winning_outcome = Column(Text, nullable=True)

    event = relationship("Event", back_populates="markets")
    outcomes = relationship("Outcome", back_populates="market")

    __table_args__ = (
        Index("idx_markets_category", "category"),
        Index("idx_markets_created_at", "created_at"),
        Index("idx_markets_event_id", "event_id"),
    )


class Outcome(Base):
    __tablename__ = "outcomes"

    id = Column(Text, primary_key=True)
    market_id = Column(Text, ForeignKey("markets.id"), nullable=False)
    label = Column(Text, nullable=False)
    price = Column(Numeric(28, 12), nullable=True)
    winner = Column(Boolean, nullable=True)

    market = relationship("Market", back_populates="outcomes")

    __table_args__ = (
        Index("idx_outcomes_market_id", "market_id"),
    )


class Wallet(Base):
    __tablename__ = "wallets"

    wallet = Column(Text, primary_key=True)
    main_wallet = Column(Text, nullable=True)
    label = Column(Text, nullable=True)
    is_tracked = Column(Boolean, nullable=False, default=True)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    last_position_sync = Column(DateTime(timezone=True), nullable=True)
    last_trade_sync = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_wallets_is_tracked", "is_tracked"),
    )


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Text, primary_key=True)
    wallet = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    market_id = Column(Text, ForeignKey("markets.id"), nullable=False)
    outcome_id = Column(Text, ForeignKey("outcomes.id"), nullable=True)
    side = Column(Enum(TradeSide), nullable=False)  # type: ignore[var-annotated]
    type = Column(Enum(TradeType), nullable=True)  # type: ignore[var-annotated]
    price = Column(Numeric(28, 12), nullable=False)
    shares = Column(Numeric(28, 12), nullable=False)
    amount_usd = Column(Numeric(28, 12), nullable=False)
    fee_usd = Column(Numeric(28, 12), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    tx_hash = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_trades_wallet_ts", "wallet", text("timestamp DESC")),
        Index("idx_trades_market", "market_id"),
        Index("idx_trades_timestamp", "timestamp"),
    )


class Position(Base):
    __tablename__ = "positions"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    market_id = Column(Text, ForeignKey("markets.id"), primary_key=True)
    outcome_id = Column(Text, ForeignKey("outcomes.id"), nullable=True)
    side = Column(Enum(TradeSide), nullable=True)  # type: ignore[var-annotated]
    status = Column(  # type: ignore[var-annotated]
        Enum(PositionStatus), nullable=False, default=PositionStatus.OPEN
    )
    avg_entry_price = Column(Numeric(28, 12), nullable=True)
    shares = Column(Numeric(28, 12), nullable=True)
    entry_time = Column(DateTime(timezone=True), nullable=True)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    realized_pnl = Column(Numeric(28, 12), nullable=True)
    unrealized_pnl = Column(Numeric(28, 12), nullable=True)
    total_pnl = Column(Numeric(28, 12), nullable=True)

    __table_args__ = (
        Index("idx_positions_wallet", "wallet"),
        Index("idx_positions_market", "market_id"),
    )


class PositionHistory(Base):
    __tablename__ = "position_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    market_id = Column(Text, ForeignKey("markets.id"), nullable=False)
    outcome_id = Column(Text, ForeignKey("outcomes.id"), nullable=True)
    side = Column(Enum(TradeSide), nullable=True)  # type: ignore[var-annotated]
    shares_before = Column(Numeric(28, 12), nullable=True)
    shares_after = Column(Numeric(28, 12), nullable=True)
    pnl_change = Column(Numeric(28, 12), nullable=True)
    recorded_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WalletAnalytic(Base):
    __tablename__ = "wallet_analytics"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    total_pnl = Column(Numeric(28, 2), nullable=True)
    total_realized_pnl = Column(Numeric(28, 2), nullable=True)
    total_unrealized_pnl = Column(Numeric(28, 2), nullable=True)
    roi = Column(Numeric(8, 6), nullable=True)
    total_volume = Column(Numeric(28, 2), nullable=True)
    total_cost_basis = Column(Numeric(28, 2), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    num_trades = Column(Integer, nullable=True)
    num_resolved_positions = Column(Integer, nullable=True)
    profit_factor = Column(Numeric(28, 6), nullable=True)
    sharpe_ratio = Column(Numeric(8, 6), nullable=True)
    max_drawdown = Column(Numeric(8, 6), nullable=True)
    avg_position_size = Column(Numeric(28, 2), nullable=True)
    avg_holding_duration = Column(Interval, nullable=True)
    consistency_score = Column(Numeric(8, 6), nullable=True)
    experience_score = Column(Numeric(8, 6), nullable=True)
    wallet_score = Column(Numeric(8, 6), nullable=True)

    __table_args__ = (
        Index(
            "idx_wallet_analytics_date_score",
            "snapshot_date",
            text("wallet_score DESC NULLS LAST"),
        ),
    )


class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    list_type = Column(Text, primary_key=True)
    rank = Column(Integer, nullable=False)
    wallet_score = Column(Numeric(8, 6), nullable=True)
    roi = Column(Numeric(8, 6), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    consistency_score = Column(Numeric(8, 6), nullable=True)
    experience_score = Column(Numeric(8, 6), nullable=True)
    risk_adj_return = Column(Numeric(8, 6), nullable=True)
    total_pnl = Column(Numeric(28, 2), nullable=True)
    num_trades = Column(Integer, nullable=True)

    __table_args__ = (
        Index(
            "idx_rankings_list_date_score",
            "snapshot_date",
            "list_type",
            "rank",
        ),
    )
