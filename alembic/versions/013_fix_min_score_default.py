"""Fix min_score default from 80 to 0.80 to match wallet_score range [0, 1.0]"""

from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"


def upgrade() -> None:
    op.alter_column(
        "alert_rules",
        "min_score",
        server_default=sa.text("0.80"),
        existing_type=sa.Numeric(8, 6),
        existing_nullable=False,
    )
    op.execute("UPDATE alert_rules SET min_score = 0.80 WHERE wallet IS NULL")
    op.execute("UPDATE alert_rules SET min_score = 0.80 WHERE min_score > 1.0")


def downgrade() -> None:
    op.alter_column(
        "alert_rules",
        "min_score",
        server_default=sa.text("80.0"),
        existing_type=sa.Numeric(8, 6),
        existing_nullable=False,
    )
    op.execute("UPDATE alert_rules SET min_score = 80.0 WHERE wallet IS NULL")
