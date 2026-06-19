"""Add mapped_category column to markets table.

Revision ID: 003
Revises: 002
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("markets", sa.Column("mapped_category", sa.Text(), nullable=True))
    op.create_index("idx_markets_mapped_category", "markets", ["mapped_category"])


def downgrade() -> None:
    op.drop_index("idx_markets_mapped_category")
    op.drop_column("markets", "mapped_category")
