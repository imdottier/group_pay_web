"""seed predefined bill categories

Revision ID: a1001cfc7236
Revises: da121b1aebfb
Create Date: 2025-06-10 00:35:12.999312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1001cfc7236'
down_revision: Union[str, None] = 'da121b1aebfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
