"""Add category_analytics and category_rankings tables.

Revision ID: 002
Revises: 001
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "category_analytics",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column("total_volume", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_cost_basis", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_realized_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_unrealized_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("roi", sa.Numeric(28, 6), nullable=True),
        sa.Column("win_rate", sa.Numeric(28, 6), nullable=True),
        sa.Column("num_resolved_positions", sa.Integer(), nullable=True),
        sa.Column("profit_factor", sa.Numeric(28, 6), nullable=True),
        sa.Column("avg_position_size", sa.Numeric(28, 2), nullable=True),
        sa.Column("avg_holding_duration", sa.Interval(), nullable=True),
        sa.Column(
            "is_specialist",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("category_rank", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["wallet"],
            ["wallets.wallet"],
            name="fk_cat_analytics_wallet",
        ),
        sa.PrimaryKeyConstraint("wallet", "category", "snapshot_date"),
    )
    op.create_index(
        "idx_cat_analytics_leaderboard",
        "category_analytics",
        ["snapshot_date", "category", "category_rank"],
    )
    op.create_index(
        "idx_cat_analytics_wallet_date",
        "category_analytics",
        ["wallet", "snapshot_date"],
    )

    op.create_table(
        "category_rankings",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("list_type", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("wallet_score", sa.Numeric(28, 6), nullable=True),
        sa.Column("roi", sa.Numeric(28, 6), nullable=True),
        sa.Column("win_rate", sa.Numeric(28, 6), nullable=True),
        sa.Column("total_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("num_trades", sa.Integer(), nullable=True),
        sa.Column("total_volume", sa.Numeric(28, 2), nullable=True),
        sa.ForeignKeyConstraint(
            ["wallet"],
            ["wallets.wallet"],
            name="fk_cat_rankings_wallet",
        ),
        sa.PrimaryKeyConstraint("wallet", "category", "snapshot_date", "list_type"),
    )
    op.create_index(
        "idx_cat_rankings_list",
        "category_rankings",
        ["snapshot_date", "category", "list_type", "rank"],
    )


def downgrade() -> None:
    op.drop_table("category_rankings")
    op.drop_table("category_analytics")
