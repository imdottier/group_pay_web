"""Add admin role to GroupRole enum

Revision ID: fdf79256e4b6
Revises: aeab26d5c639
Create Date: 2025-05-09 00:56:55.654089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'fdf79256e4b6'
down_revision: Union[str, None] = 'aeab26d5c639'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

enum_name = 'grouprole' # Common default name generated by SQLAlchemy, check your model/DB if different
old_options = ('owner', 'member')
new_options = ('owner', 'admin', 'member')

def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('group_members', 'role',
            existing_type=mysql.ENUM(*old_options, name=enum_name),
            type_=mysql.ENUM(*new_options, name=enum_name),
            existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('group_members', 'role',
            existing_type=mysql.ENUM(*new_options, name=enum_name),
            type_=mysql.ENUM(*old_options, name=enum_name),
            existing_nullable=False)
    # ### end Alembic commands ###
