"""fix group_invitations enum to lowercase

Revision ID: d0ddf87bfa73
Revises: 904d94f1b6da
Create Date: 2025-06-07 17:20:27.398274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0ddf87bfa73'
down_revision: Union[str, None] = '904d94f1b6da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("ALTER TABLE group_invitations MODIFY COLUMN status ENUM('pending', 'accepted', 'declined') NOT NULL")
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("ALTER TABLE group_invitations MODIFY COLUMN status ENUM('PENDING', 'ACCEPTED', 'DECLINED') NOT NULL")
    # ### end Alembic commands ###
