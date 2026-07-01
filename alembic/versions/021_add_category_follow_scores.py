"""Add wallet_category_follow_scores table and category_follow_scores column for Phase 5.

Revision ID: 021
Revises: 020
Create Date: 2026-06-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_category_follow_scores",
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("follow_score", sa.Numeric(8, 6), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("roi_percentile", sa.Numeric(8, 6), nullable=True),
        sa.Column("win_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("is_specialist", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("volume_percentile", sa.Numeric(8, 6), nullable=True),
        sa.Column("recency_days", sa.Integer(), nullable=True),
        sa.Column("reasons", postgresql.JSONB(), nullable=True),
        sa.Column("global_follow_score", sa.Numeric(8, 6), nullable=True),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"], name="fk_cat_follow_wallet"),
        sa.ForeignKeyConstraint(["category"], ["categories.category"], name="fk_cat_follow_category"),
        sa.PrimaryKeyConstraint("wallet", "category", "snapshot_date"),
    )
    op.create_index("idx_cat_follow_scores_score", "wallet_category_follow_scores",
                    ["category", sa.text("follow_score DESC")])
    op.create_index("idx_cat_follow_scores_wallet", "wallet_category_follow_scores",
                    ["wallet", sa.text("snapshot_date DESC")])
    op.create_index("idx_cat_follow_scores_rec", "wallet_category_follow_scores",
                    ["category", "recommendation"],
                    postgresql_where=sa.text("recommendation = 'FOLLOW'"))

    op.add_column(
        "wallet_analytics",
        sa.Column("category_follow_scores", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wallet_analytics", "category_follow_scores")
    op.drop_index("idx_cat_follow_scores_rec", table_name="wallet_category_follow_scores")
    op.drop_index("idx_cat_follow_scores_wallet", table_name="wallet_category_follow_scores")
    op.drop_index("idx_cat_follow_scores_score", table_name="wallet_category_follow_scores")
    op.drop_table("wallet_category_follow_scores")
