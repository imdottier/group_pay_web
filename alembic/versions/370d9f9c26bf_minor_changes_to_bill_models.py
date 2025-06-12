"""minor changes to bill models

Revision ID: 370d9f9c26bf
Revises: b01a1f7b69e2
Create Date: 2025-05-11 15:30:28.226174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '370d9f9c26bf'
down_revision: Union[str, None] = 'b01a1f7b69e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
