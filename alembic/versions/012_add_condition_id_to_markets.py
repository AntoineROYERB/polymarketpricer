"""Add condition_id column to markets table.

This column stores the Polymarket conditionId from Gamma API, used by
data loaders (positions, trades, activity) to map assets to market IDs.

Revision ID: 012
Revises: 011
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("markets", sa.Column("condition_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("markets", "condition_id")
