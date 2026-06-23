"""Drop outcome_id FK constraints from positions and position_history.

These FKs reference outcomes.id, but the positions pipeline uses
outcome_id values from the Data API (64-byte token addresses) which
do not match the local outcomes.id format (market_id_i).

Revision ID: 006
Revises: 005
Create Date: 2026-06-22
"""

from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE positions DROP CONSTRAINT IF EXISTS positions_outcome_id_fkey"
    )
    op.execute(
        "ALTER TABLE position_history "
        "DROP CONSTRAINT IF EXISTS position_history_outcome_id_fkey"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE positions "
        "ADD CONSTRAINT positions_outcome_id_fkey "
        "FOREIGN KEY (outcome_id) REFERENCES outcomes(id)"
    )
    op.execute(
        "ALTER TABLE position_history "
        "ADD CONSTRAINT position_history_outcome_id_fkey "
        "FOREIGN KEY (outcome_id) REFERENCES outcomes(id)"
    )
