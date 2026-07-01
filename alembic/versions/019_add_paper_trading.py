"""Add paper_portfolios, paper_positions, paper_trades tables for Phase 5.

Revision ID: 019
Revises: 018
Create Date: 2026-06-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_portfolios",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False, server_default=sa.text("'Main'")),
        sa.Column("initial_balance", sa.Numeric(28, 2), nullable=False),
        sa.Column("current_balance", sa.Numeric(28, 2), nullable=False),
        sa.CheckConstraint("current_balance >= 0", name="ck_portfolio_balance_non_negative"),
        sa.Column("total_realized_pnl", sa.Numeric(28, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_unrealized_pnl", sa.Numeric(28, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_pnl", sa.Numeric(28, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_roi", sa.Numeric(28, 6), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_volume", sa.Numeric(28, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_portfolios_user", "paper_portfolios", ["user_id"])

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'OPEN'")),
        sa.Column("shares", sa.Numeric(28, 12), nullable=False),
        sa.CheckConstraint("shares >= 0", name="ck_position_shares_non_negative"),
        sa.Column("avg_entry_price", sa.Numeric(28, 12), nullable=False),
        sa.Column("current_price", sa.Numeric(28, 12), nullable=True),
        sa.Column("cost_basis", sa.Numeric(28, 2), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(28, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("unrealized_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("followed_wallet", sa.Text(), nullable=False),
        sa.Column("source_alert_id", sa.Uuid(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolios.id"], name="fk_pp_portfolio"),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"], name="fk_pp_market"),
        sa.ForeignKeyConstraint(["followed_wallet"], ["wallets.wallet"], name="fk_pp_followed_wallet"),
        sa.ForeignKeyConstraint(["source_alert_id"], ["alerts.id"], name="fk_pp_source_alert", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_paper_positions_portfolio", "paper_positions", ["portfolio_id", "status"])
    op.create_index("idx_paper_positions_market", "paper_positions", ["market_id"])
    op.create_index("idx_paper_positions_followed", "paper_positions", ["followed_wallet"])

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=True),
        sa.Column("source_alert_id", sa.Uuid(), nullable=True),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=False),
        sa.Column("shares", sa.Numeric(28, 12), nullable=False),
        sa.Column("amount_usd", sa.Numeric(28, 2), nullable=False),
        sa.Column("followed_wallet", sa.Text(), nullable=False),
        sa.Column("copy_mode", sa.Text(), nullable=True),
        sa.Column("copy_value_used", sa.Numeric(28, 6), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolios.id"], name="fk_pt_portfolio"),
        sa.ForeignKeyConstraint(["position_id"], ["paper_positions.id"], name="fk_pt_position"),
        sa.ForeignKeyConstraint(["source_alert_id"], ["alerts.id"], name="fk_pt_source_alert", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"], name="fk_pt_market"),
        sa.ForeignKeyConstraint(["followed_wallet"], ["wallets.wallet"], name="fk_pt_followed_wallet"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_paper_trades_portfolio", "paper_trades", ["portfolio_id", sa.text("executed_at DESC")])
    op.create_index("idx_paper_trades_market", "paper_trades", ["market_id"])
    op.create_index("idx_paper_trades_followed", "paper_trades", ["followed_wallet"])
    op.create_index("idx_paper_trades_source_alert", "paper_trades", ["source_alert_id"])


def downgrade() -> None:
    op.drop_index("idx_paper_trades_source_alert", table_name="paper_trades")
    op.drop_index("idx_paper_trades_followed", table_name="paper_trades")
    op.drop_index("idx_paper_trades_market", table_name="paper_trades")
    op.drop_index("idx_paper_trades_portfolio", table_name="paper_trades")
    op.drop_table("paper_trades")
    op.drop_index("idx_paper_positions_followed", table_name="paper_positions")
    op.drop_index("idx_paper_positions_market", table_name="paper_positions")
    op.drop_index("idx_paper_positions_portfolio", table_name="paper_positions")
    op.drop_table("paper_positions")
    op.drop_index("idx_portfolios_user", table_name="paper_portfolios")
    op.drop_table("paper_portfolios")
