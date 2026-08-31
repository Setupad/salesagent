"""merge heads for VPS deploy

Revision ID: ec376a1c7624
Revises: 9b2d4f6c1a37, b7c9e4a2d6f1
Create Date: 2026-08-31 18:03:17.355441

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec376a1c7624'
down_revision: Union[str, Sequence[str], None] = ('9b2d4f6c1a37', 'b7c9e4a2d6f1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
