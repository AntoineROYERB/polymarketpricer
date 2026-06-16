# Initial migration: create all tables with final schema

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE tradeside AS ENUM ('BUY', 'SELL')")
    op.execute("CREATE TYPE tradetype AS ENUM ('MARKET', 'LIMIT')")
    op.execute("CREATE TYPE positionstatus AS ENUM ('OPEN', 'CLOSED', 'RESOLVED')")

    op.create_table(
        "events",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "markets",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("event_id", sa.Text(), nullable=True),
        sa.Column("event_slug", sa.Text(), nullable=True),
        sa.Column("volume_usd", sa.Numeric(28, 2), nullable=True),
        sa.Column("liquidity_usd", sa.Numeric(28, 2), nullable=True),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("winning_outcome", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_markets_category", "markets", ["category"])
    op.create_index("idx_markets_created_at", "markets", ["created_at"])
    op.create_index("idx_markets_event_id", "markets", ["event_id"])

    op.create_table(
        "outcomes",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=True),
        sa.Column("winner", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_outcomes_market_id", "outcomes", ["market_id"])

    op.create_table(
        "wallets",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("main_wallet", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("is_tracked", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_position_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_trade_sync", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("wallet"),
    )
    op.create_index("idx_wallets_is_tracked", "wallets", ["is_tracked"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("outcome_id", sa.Text(), nullable=True),
        sa.Column(
            "side",
            postgresql.ENUM("BUY", "SELL", name="tradeside", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM("MARKET", "LIMIT", name="tradetype", create_type=False),
            nullable=True,
        ),
        sa.Column("price", sa.Numeric(28, 12), nullable=False),
        sa.Column("shares", sa.Numeric(28, 12), nullable=False),
        sa.Column("amount_usd", sa.Numeric(28, 12), nullable=False),
        sa.Column("fee_usd", sa.Numeric(28, 12), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_hash", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"],),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"],),
        sa.ForeignKeyConstraint(["outcome_id"], ["outcomes.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_trades_wallet_ts",
        "trades",
        ["wallet", sa.text("timestamp DESC")],
    )
    op.create_index("idx_trades_market", "trades", ["market_id"])
    op.create_index("idx_trades_timestamp", "trades", ["timestamp"])

    op.create_table(
        "positions",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("outcome_id", sa.Text(), nullable=True),
        sa.Column(
            "side",
            postgresql.ENUM("BUY", "SELL", name="tradeside", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("OPEN", "CLOSED", "RESOLVED", name="positionstatus", create_type=False),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("avg_entry_price", sa.Numeric(28, 12), nullable=True),
        sa.Column("shares", sa.Numeric(28, 12), nullable=True),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(28, 12), nullable=True),
        sa.Column("unrealized_pnl", sa.Numeric(28, 12), nullable=True),
        sa.Column("total_pnl", sa.Numeric(28, 12), nullable=True),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"],),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"],),
        sa.ForeignKeyConstraint(["outcome_id"], ["outcomes.id"],),
        sa.PrimaryKeyConstraint("wallet", "market_id"),
    )
    op.create_index("idx_positions_wallet", "positions", ["wallet"])
    op.create_index("idx_positions_market", "positions", ["market_id"])

    op.create_table(
        "position_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("outcome_id", sa.Text(), nullable=True),
        sa.Column(
            "side",
            postgresql.ENUM("BUY", "SELL", name="tradeside", create_type=False),
            nullable=True,
        ),
        sa.Column("shares_before", sa.Numeric(28, 12), nullable=True),
        sa.Column("shares_after", sa.Numeric(28, 12), nullable=True),
        sa.Column("pnl_change", sa.Numeric(28, 12), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"],),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"],),
        sa.ForeignKeyConstraint(["outcome_id"], ["outcomes.id"],),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "wallet_analytics",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_realized_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_unrealized_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("roi", sa.Numeric(8, 6), nullable=True),
        sa.Column("total_volume", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_cost_basis", sa.Numeric(28, 2), nullable=True),
        sa.Column("win_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column("num_resolved_positions", sa.Integer(), nullable=True),
        sa.Column("profit_factor", sa.Numeric(28, 6), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(8, 6), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(8, 6), nullable=True),
        sa.Column("avg_position_size", sa.Numeric(28, 2), nullable=True),
        sa.Column("avg_holding_duration", sa.Interval(), nullable=True),
        sa.Column("consistency_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("experience_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("wallet_score", sa.Numeric(8, 6), nullable=True),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"],),
        sa.PrimaryKeyConstraint("wallet", "snapshot_date"),
    )
    op.create_index(
        "idx_wallet_analytics_date_score",
        "wallet_analytics",
        ["snapshot_date", sa.text("wallet_score DESC NULLS LAST")],
    )

    op.create_table(
        "ranking_snapshots",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("list_type", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("wallet_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("roi", sa.Numeric(8, 6), nullable=True),
        sa.Column("win_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("consistency_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("experience_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("risk_adj_return", sa.Numeric(8, 6), nullable=True),
        sa.Column("total_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"],),
        sa.PrimaryKeyConstraint("wallet", "snapshot_date", "list_type"),
    )
    op.create_index(
        "idx_rankings_list_date_score",
        "ranking_snapshots",
        ["snapshot_date", "list_type", "rank"],
    )


def downgrade() -> None:
    for table in reversed([
        "ranking_snapshots",
        "wallet_analytics",
        "position_history",
        "positions",
        "trades",
        "wallets",
        "outcomes",
        "markets",
        "events",
    ]):
        op.drop_table(table)
    op.execute("DROP TYPE IF EXISTS tradeside")
    op.execute("DROP TYPE IF EXISTS tradetype")
    op.execute("DROP TYPE IF EXISTS positionstatus")
