"""Increase ranking_snapshots numeric precision from (8,6) to (28,6).

ROI can exceed 99.999999 (e.g. a wallet with 10841% return), which
causes NumericValueOutOfRange errors when the ranking pipeline writes
raw wallet_analytics values into ranking_snapshots.

Migration 015 already bumped the same columns in wallet_analytics;
this completes the fix for the ranking_snapshots table.

Affected columns: roi, win_rate, consistency_score, experience_score,
                  risk_adj_return, wallet_score
"""

from alembic import op
import sqlalchemy as sa


revision = "016"
down_revision = "015"


def upgrade() -> None:
    for col in (
        "roi",
        "win_rate",
        "consistency_score",
        "experience_score",
        "risk_adj_return",
        "wallet_score",
    ):
        op.alter_column(
            "ranking_snapshots",
            col,
            type_=sa.Numeric(28, 6),
            postgresql_using=f"{col}::numeric(28,6)",
        )


def downgrade() -> None:
    for col in (
        "roi",
        "win_rate",
        "consistency_score",
        "experience_score",
        "risk_adj_return",
        "wallet_score",
    ):
        op.alter_column(
            "ranking_snapshots",
            col,
            type_=sa.Numeric(8, 6),
            postgresql_using=f"{col}::numeric(8,6)",
        )
