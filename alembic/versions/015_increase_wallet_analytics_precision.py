"""Increase wallet_analytics numeric precision from (8,6) to (28,6).

ROI and sharpe_ratio can exceed 99.999999, causing NumericValueOutOfRange errors.
Harmonise all NUMERIC(8,6) columns to NUMERIC(28,6) for consistency.
"""

from alembic import op
import sqlalchemy as sa


revision = "015"
down_revision = "014"


def upgrade() -> None:
    for col in ("roi", "win_rate", "sharpe_ratio", "max_drawdown",
                "consistency_score", "experience_score", "wallet_score"):
        op.alter_column("wallet_analytics", col,
                        type_=sa.Numeric(28, 6),
                        postgresql_using=f"{col}::numeric(28,6)")


def downgrade() -> None:
    for col in ("roi", "win_rate", "sharpe_ratio", "max_drawdown",
                "consistency_score", "experience_score", "wallet_score"):
        op.alter_column("wallet_analytics", col,
                        type_=sa.Numeric(8, 6),
                        postgresql_using=f"{col}::numeric(8,6)")
