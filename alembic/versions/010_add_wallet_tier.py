"""Add tier column to wallets for tier-based sync frequency.

Tier 1: daily sync (smart money)
Tier 2: every 3 days (intermediate)
Tier 3: weekly (long tail, default)

Revision ID: 010
Revises: 009
Create Date: 2026-06-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallets",
        sa.Column("tier", sa.Integer(), nullable=False, server_default=sa.text("3")),
    )
    op.create_index("idx_wallets_tier", "wallets", ["tier"])


def downgrade() -> None:
    op.drop_column("wallets", "tier")
