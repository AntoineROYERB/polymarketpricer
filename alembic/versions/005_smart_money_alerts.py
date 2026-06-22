"""Add alerts and alert_rules tables for Phase 3 Smart Money Detection.

Revision ID: 005
Revises: 004
Create Date: 2026-06-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("wallet", sa.Text(), nullable=True, unique=True),
        sa.Column("min_score", sa.Numeric(8, 6), nullable=False, server_default=sa.text("80.0")),
        sa.Column("min_position_size", sa.Numeric(28, 2), nullable=False, server_default=sa.text("500")),
        sa.Column("min_liquidity", sa.Numeric(28, 2), nullable=False, server_default=sa.text("1000")),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default=sa.text("15")),
        sa.Column("discord_webhook_url", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("market_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=False),
        sa.Column("position_size", sa.Numeric(28, 2), nullable=False),
        sa.Column("wallet_score", sa.Numeric(8, 6), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("market_question", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"], name="fk_alerts_wallet"),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"], name="fk_alerts_market"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_alerts_detected_at", "alerts", [sa.text("detected_at DESC")])
    op.create_index("idx_alerts_wallet", "alerts", ["wallet"])
    op.create_index("idx_alerts_category", "alerts", ["category"])
    op.create_index(
        "idx_alerts_unnotified",
        "alerts",
        ["detected_at"],
        postgresql_where=sa.text("notified_at IS NULL"),
    )
    op.create_index("idx_alerts_wallet_market", "alerts", ["wallet", "market_id"])

    # Seed global default rule
    op.execute("""
        INSERT INTO alert_rules (wallet, min_score, min_position_size, min_liquidity, cooldown_minutes)
        VALUES (NULL, 80.0, 500, 1000, 15)
    """)


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("alert_rules")
