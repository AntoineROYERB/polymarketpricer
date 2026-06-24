"""Drop outcome_id FK constraint from trades.

Same rationale as migration 006: the trades pipeline uses outcome_id values
from the Data API (64-byte token addresses) which do not match the local
outcomes.id format (market_id_i).

Revision ID: 008
Revises: 007
Create Date: 2026-06-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_outcome_id_fkey"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE trades "
        "ADD CONSTRAINT trades_outcome_id_fkey "
        "FOREIGN KEY (outcome_id) REFERENCES outcomes(id)"
    )
