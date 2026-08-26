from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.models import Base


class WalletFollow(Base):
    __tablename__ = "wallet_follows"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    wallet = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    user_id = Column(Text, nullable=False)
    label = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, server_default=text("true"))
    auto_copy_enabled = Column(Boolean, nullable=False, server_default=text("false"))
    copy_mode = Column(Text, nullable=True)
    copy_value = Column(Numeric(28, 6), nullable=False, server_default=text("0.05"))
    category_filter = Column(JSONB, nullable=True)
    followed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    unfollowed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_follows_user_wallet_active", "user_id", "wallet",
              postgresql_where=text("active = true"), unique=True),
    )


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(Text, nullable=False)
    name = Column(Text, nullable=False, server_default=text("'Main'"), default="Main")
    initial_balance = Column(Numeric(28, 2), nullable=False)
    current_balance = Column(Numeric(28, 2), nullable=False)
    total_realized_pnl = Column(Numeric(28, 2), nullable=False, server_default=text("0"), default=0)
    total_unrealized_pnl = Column(Numeric(28, 2), nullable=False, server_default=text("0"), default=0)
    total_pnl = Column(Numeric(28, 2), nullable=False, server_default=text("0"), default=0)
    total_roi = Column(Numeric(28, 6), nullable=True)
    total_trades = Column(Integer, nullable=False, server_default=text("0"), default=0)
    total_volume = Column(Numeric(28, 2), nullable=False, server_default=text("0"), default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("current_balance >= 0", name="ck_portfolio_balance_non_negative"),
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    portfolio_id = Column(Uuid, ForeignKey("paper_portfolios.id"), nullable=False)
    market_id = Column(Text, ForeignKey("markets.id"), nullable=False)
    outcome = Column(Text, nullable=False)
    side = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'OPEN'"))
    shares = Column(Numeric(28, 12), nullable=False)

    __table_args__ = (
        CheckConstraint("shares >= 0", name="ck_position_shares_non_negative"),
    )
    avg_entry_price = Column(Numeric(28, 12), nullable=False)
    current_price = Column(Numeric(28, 12), nullable=True)
    cost_basis = Column(Numeric(28, 2), nullable=False)
    realized_pnl = Column(Numeric(28, 2), nullable=False, server_default=text("0"))
    unrealized_pnl = Column(Numeric(28, 2), nullable=True)
    followed_wallet = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    source_alert_id = Column(Uuid, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    portfolio_id = Column(Uuid, ForeignKey("paper_portfolios.id"), nullable=False)
    position_id = Column(Uuid, ForeignKey("paper_positions.id"), nullable=True)
    source_alert_id = Column(Uuid, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    market_id = Column(Text, ForeignKey("markets.id"), nullable=False)
    outcome = Column(Text, nullable=False)
    side = Column(Text, nullable=False)
    price = Column(Numeric(28, 12), nullable=False)
    shares = Column(Numeric(28, 12), nullable=False)
    amount_usd = Column(Numeric(28, 2), nullable=False)
    followed_wallet = Column(Text, ForeignKey("wallets.wallet"), nullable=False)
    copy_mode = Column(Text, nullable=True)
    copy_value_used = Column(Numeric(28, 6), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WalletCategoryFollowScore(Base):
    __tablename__ = "wallet_category_follow_scores"

    wallet = Column(Text, ForeignKey("wallets.wallet"), primary_key=True)
    category = Column(Text, ForeignKey("categories.category"), primary_key=True)
    snapshot_date = Column(Date, primary_key=True)
    follow_score = Column(Numeric(8, 6), nullable=False)
    recommendation = Column(Text, nullable=False)
    roi_percentile = Column(Numeric(8, 6), nullable=True)
    win_rate = Column(Numeric(8, 6), nullable=True)
    is_specialist = Column(Boolean, nullable=False, server_default=text("false"))
    volume_percentile = Column(Numeric(8, 6), nullable=True)
    recency_days = Column(Integer, nullable=True)
    reasons = Column(JSONB, nullable=True)
    global_follow_score = Column(Numeric(8, 6), nullable=True)
