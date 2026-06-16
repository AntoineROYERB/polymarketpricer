from sqlalchemy import Column, Date, DateTime, Index, Integer, Interval, Numeric, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Market(Base):
    __tablename__ = "markets"

    id = Column(Text, primary_key=True)
    question = Column(Text, nullable=False)
    category = Column(Text, nullable=True)
    event_slug = Column(Text, nullable=True)
    outcomes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    outcome = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_markets_category", "category"),
        Index("idx_markets_created_at", "created_at"),
    )


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Text, primary_key=True)
    wallet = Column(Text, nullable=False)
    market_id = Column(Text, nullable=False)
    side = Column(Text, nullable=False)
    price = Column(Numeric, nullable=False)
    shares = Column(Numeric, nullable=False)
    amount_usd = Column(Numeric, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_trades_wallet", "wallet"),
        Index("idx_trades_market", "market_id"),
        Index("idx_trades_timestamp", "timestamp"),
    )


class Wallet(Base):
    __tablename__ = "wallets"

    wallet = Column(Text, primary_key=True)
    main_wallet = Column(Text, nullable=True)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)


class Position(Base):
    __tablename__ = "positions"

    wallet = Column(Text, primary_key=True)
    market_id = Column(Text, primary_key=True)
    avg_entry_price = Column(Numeric, nullable=True)
    shares = Column(Numeric, nullable=True)
    realized_pnl = Column(Numeric, nullable=True)
    unrealized_pnl = Column(Numeric, nullable=True)


class WalletAnalytic(Base):
    __tablename__ = "wallet_analytics"

    wallet = Column(Text, primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    total_pnl = Column(Numeric, nullable=True)
    roi = Column(Numeric, nullable=True)
    win_rate = Column(Numeric, nullable=True)
    num_trades = Column(Integer, nullable=True)
    avg_position_size = Column(Numeric, nullable=True)
    risk_adj_return = Column(Numeric, nullable=True)
    avg_holding_duration = Column(Interval, nullable=True)
    wallet_score = Column(Numeric, nullable=True)
