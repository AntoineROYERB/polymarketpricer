"""Add index on alerts action + detected_at for new alert types.

Supports TRADE_BUY, TRADE_SELL, FIRST_MOVER alert action queries.

Revision ID: 011
Revises: 010
Create Date: 2026-06-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_alerts_action_detected",
        "alerts",
        ["action", sa.text("detected_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_alerts_action_detected")
