"""record VPS deploy head after reverted migration merge

Revision ID: f7d2c3b4a901
Revises: ec376a1c7624
Create Date: 2026-09-02 08:59:00.000000

"""

from collections.abc import Sequence


# revision identifiers, used by Alembic.
revision: str = "f7d2c3b4a901"
down_revision: str | Sequence[str] | None = "ec376a1c7624"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record the existing production Alembic head."""
    pass


def downgrade() -> None:
    """Return to the previous VPS deploy head."""
    pass
