"""Add advertiser discount percentages.

Revision ID: d3a9c6e8f210
Revises: 526ce4501041
"""

import sqlalchemy as sa

from alembic import op

revision = "d3a9c6e8f210"
down_revision = "526ce4501041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("principals", sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=False, server_default="0"))
    op.create_check_constraint(
        "ck_principals_discount_percentage", "principals", "discount_percentage >= 0 AND discount_percentage <= 99.99"
    )


def downgrade() -> None:
    op.drop_constraint("ck_principals_discount_percentage", "principals", type_="check")
    op.drop_column("principals", "discount_percentage")
