"""Add wallet_follows table for Phase 5.

Revision ID: 018
Revises: 017
Create Date: 2026-06-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_follows",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("wallet", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_copy_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("copy_mode", sa.Text(), nullable=True),
        sa.Column("copy_value", sa.Numeric(28, 6), nullable=False, server_default=sa.text("0.05")),
        sa.Column("category_filter", postgresql.JSONB(), nullable=True),
        sa.Column("followed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("unfollowed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["wallet"], ["wallets.wallet"], name="fk_follows_wallet"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_follows_user_wallet_active", "wallet_follows", ["user_id", "wallet"],
                    postgresql_where=sa.text("active = true"), unique=True)
    op.create_index("idx_follows_user_active", "wallet_follows", ["user_id", "active"],
                    postgresql_where=sa.text("active = true"))
    op.create_index("idx_follows_wallet", "wallet_follows", ["wallet"])
    op.create_index("idx_follows_auto_copy", "wallet_follows", ["auto_copy_enabled"],
                    postgresql_where=sa.text("auto_copy_enabled = true"))


def downgrade() -> None:
    op.drop_index("uq_follows_user_wallet_active", table_name="wallet_follows")
    op.drop_index("idx_follows_auto_copy", table_name="wallet_follows")
    op.drop_index("idx_follows_wallet", table_name="wallet_follows")
    op.drop_index("idx_follows_user_active", table_name="wallet_follows")
    op.drop_table("wallet_follows")
