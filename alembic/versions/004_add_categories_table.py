"""Add categories lookup table with label and FK constraints.

Revision ID: 004
Revises: 003
Create Date: 2026-06-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("category"),
    )

    categories_data = [
        ("Politics", "Politics & Governance"),
        ("Crypto", "Cryptocurrency & Blockchain"),
        ("Sports", "Sports & Betting"),
        ("Economics", "Economics & Finance"),
        ("Technology", "Technology & Innovation"),
        ("AI", "Artificial Intelligence"),
        ("Geopolitics", "Geopolitics & World Affairs"),
        ("Entertainment", "Entertainment & Pop Culture"),
    ]
    for cat, label in categories_data:
        op.execute(
            f"INSERT INTO categories (category, label) VALUES ('{cat}', '{label}')"
        )

    op.create_foreign_key(
        "fk_cat_analytics_category",
        "category_analytics",
        "categories",
        ["category"],
        ["category"],
    )
    op.create_foreign_key(
        "fk_cat_rankings_category",
        "category_rankings",
        "categories",
        ["category"],
        ["category"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_cat_analytics_category", "category_analytics", type_="foreignkey")
    op.drop_constraint("fk_cat_rankings_category", "category_rankings", type_="foreignkey")
    op.drop_table("categories")
