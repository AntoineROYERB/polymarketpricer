"""Add indexes for incremental sync queries.

Adds composite indexes on wallets for the WHERE + ORDER BY clauses used
by incremental sync queries (is_tracked + last_position_sync / last_trade_sync),
plus indexes on position_history and markets for smart money detection.

Revision ID: 009
Revises: 008
Create Date: 2026-06-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_wallets_sync_position",
        "wallets",
        ["is_tracked", sa.text("last_position_sync NULLS FIRST")],
    )
    op.create_index(
        "idx_wallets_sync_trade",
        "wallets",
        ["is_tracked", sa.text("last_trade_sync NULLS FIRST")],
    )
    op.create_index(
        "idx_position_history_recorded_at",
        "position_history",
        ["recorded_at"],
    )
    op.create_index(
        "idx_markets_created_at_id",
        "markets",
        ["created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_wallets_sync_position")
    op.drop_index("idx_wallets_sync_trade")
    op.drop_index("idx_position_history_recorded_at")
    op.drop_index("idx_markets_created_at_id")
