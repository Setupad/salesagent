"""merge synced upstream and VPS deployment heads

Revision ID: 526ce4501041
Revises: 7f31c0ab94d2, f7d2c3b4a901
Create Date: 2026-10-23 15:29:42.660597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '526ce4501041'
down_revision: Union[str, Sequence[str], None] = ('7f31c0ab94d2', 'f7d2c3b4a901')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
