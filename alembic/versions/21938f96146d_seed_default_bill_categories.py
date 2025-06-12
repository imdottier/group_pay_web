"""seed default bill categories

Revision ID: 21938f96146d
Revises: 7c9719cbe5a2
Create Date: 2025-06-10 01:10:20.942398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21938f96146d'
down_revision: Union[str, None] = '7c9719cbe5a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the table structure for use in the migration
bill_categories_table = sa.table(
    'bill_categories',
    sa.column('name', sa.String),
    sa.column('group_id', sa.Integer)
)

DEFAULT_CATEGORIES = [
    {'name': 'Food & Dining'},
    {'name': 'Transportation'},
    {'name': 'Utilities'},
    {'name': 'Shopping'},
    {'name': 'Miscellaneous'},
]


def upgrade() -> None:
    """Seed default bill categories."""
    op.bulk_insert(
        bill_categories_table,
        DEFAULT_CATEGORIES
    )


def downgrade() -> None:
    """Remove default bill categories."""
    # This will delete all default categories (where group_id is NULL)
    op.execute(
        bill_categories_table.delete().where(
            bill_categories_table.c.group_id.is_(None)
        )
    )
