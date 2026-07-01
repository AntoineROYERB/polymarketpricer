"""Add follow_score column to wallet_analytics for Phase 5.

Revision ID: 020
Revises: 019
Create Date: 2026-06-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallet_analytics",
        sa.Column("follow_score", sa.Numeric(8, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wallet_analytics", "follow_score")
