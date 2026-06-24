"""Add wallet_pnl_snapshots table for cashflow-based PnL.

Revision ID: 007
Revises: 006
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_pnl_snapshots",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),

        sa.Column("total_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_realized_pnl", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_unrealized_pnl", sa.Numeric(28, 2), nullable=True),

        sa.Column("total_bought", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_sold", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_redeemed", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_merged", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_split", sa.Numeric(28, 2), nullable=True),
        sa.Column("total_rebates", sa.Numeric(28, 2), nullable=True),

        sa.Column("category_breakdown", JSONB(), nullable=True),

        sa.Column("num_activity_events", sa.Integer(), nullable=True),
        sa.Column("open_position_value", sa.Numeric(28, 2), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),

        sa.ForeignKeyConstraint(
            ["wallet"], ["wallets.wallet"],
            name="fk_pnl_snapshot_wallet",
        ),
        sa.PrimaryKeyConstraint("wallet", "snapshot_date"),
    )
    op.create_index(
        "idx_pnl_snapshots_date",
        "wallet_pnl_snapshots",
        ["snapshot_date"],
    )
    op.create_index(
        "idx_pnl_snapshots_wallet_date",
        "wallet_pnl_snapshots",
        ["wallet", sa.text("snapshot_date DESC")],
    )


def downgrade() -> None:
    op.drop_table("wallet_pnl_snapshots")
