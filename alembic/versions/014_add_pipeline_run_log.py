"""Add pipeline_run_log table for cross-process ETL orchestration status."""

from alembic import op
import sqlalchemy as sa


revision = "014"
down_revision = "013"


def upgrade() -> None:
    op.create_table(
        "pipeline_run_log",
        sa.Column("pipeline_name", sa.Text(), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pipeline_run_log_updated_at", "pipeline_run_log", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_run_log_updated_at")
    op.drop_table("pipeline_run_log")
