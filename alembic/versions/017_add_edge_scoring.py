"""Add wallet_edge_snapshots table and edge_score columns for Phase 4 Edge Scoring.

Revision ID: 017
Revises: 016
Create Date: 2026-06-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_edge_snapshots",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("avg_edge", sa.Numeric(28, 6), nullable=False),
        sa.Column("median_edge", sa.Numeric(28, 6), nullable=True),
        sa.Column("edge_consistency", sa.Numeric(8, 6), nullable=True),
        sa.Column("edge_volatility", sa.Numeric(28, 6), nullable=True),
        sa.Column("edge_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("num_edge_trades", sa.Integer(), nullable=False),
        sa.Column("positive_edge_trades", sa.Integer(), nullable=True),
        sa.Column("negative_edge_trades", sa.Integer(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["wallet"], ["wallets.wallet"], name="fk_ws_wallet"
        ),
        sa.PrimaryKeyConstraint("wallet", "snapshot_date"),
    )
    op.create_index(
        "idx_ws_wallet_date",
        "wallet_edge_snapshots",
        ["wallet", sa.text("snapshot_date DESC")],
    )
    op.create_index(
        "idx_ws_date",
        "wallet_edge_snapshots",
        [sa.text("snapshot_date DESC")],
    )
    op.create_index(
        "idx_ws_edge_score",
        "wallet_edge_snapshots",
        [sa.text("edge_score DESC")],
    )
    op.add_column(
        "wallet_analytics",
        sa.Column("edge_score", sa.Numeric(8, 6), nullable=True),
    )
    op.add_column(
        "ranking_snapshots",
        sa.Column("edge_score", sa.Numeric(8, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ranking_snapshots", "edge_score")
    op.drop_column("wallet_analytics", "edge_score")
    op.drop_index("idx_ws_edge_score", table_name="wallet_edge_snapshots")
    op.drop_index("idx_ws_date", table_name="wallet_edge_snapshots")
    op.drop_index("idx_ws_wallet_date", table_name="wallet_edge_snapshots")
    op.drop_table("wallet_edge_snapshots")
