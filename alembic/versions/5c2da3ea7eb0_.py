"""empty message

Revision ID: 5c2da3ea7eb0
Revises: e45294584bc2
Create Date: 2025-06-06 22:56:24.705892

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c2da3ea7eb0'
down_revision: Union[str, None] = 'e45294584bc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
