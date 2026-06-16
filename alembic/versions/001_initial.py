# Initial migration: create all tables

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("event_slug", sa.Text(), nullable=True),
        sa.Column("outcomes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_markets_category", "markets", ["category"])
    op.create_index("idx_markets_created_at", "markets", ["created_at"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("shares", sa.Numeric(), nullable=False),
        sa.Column("amount_usd", sa.Numeric(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_trades_wallet", "trades", ["wallet"])
    op.create_index("idx_trades_market", "trades", ["market_id"])
    op.create_index("idx_trades_timestamp", "trades", ["timestamp"])

    op.create_table(
        "wallets",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("main_wallet", sa.Text(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("wallet"),
    )

    op.create_table(
        "positions",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("avg_entry_price", sa.Numeric(), nullable=True),
        sa.Column("shares", sa.Numeric(), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(), nullable=True),
        sa.Column("unrealized_pnl", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("wallet", "market_id"),
    )

    op.create_table(
        "wallet_analytics",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_pnl", sa.Numeric(), nullable=True),
        sa.Column("roi", sa.Numeric(), nullable=True),
        sa.Column("win_rate", sa.Numeric(), nullable=True),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column("avg_position_size", sa.Numeric(), nullable=True),
        sa.Column("risk_adj_return", sa.Numeric(), nullable=True),
        sa.Column("avg_holding_duration", sa.Interval(), nullable=True),
        sa.Column("wallet_score", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("wallet", "snapshot_date"),
    )


def downgrade() -> None:
    op.drop_table("wallet_analytics")
    op.drop_table("positions")
    op.drop_table("wallets")
    op.drop_table("trades")
    op.drop_table("markets")
