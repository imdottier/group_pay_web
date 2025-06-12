"""Add notification type enum

Revision ID: dd8c8ee9c343
Revises: 4a92f3cde7d9
Create Date: 2025-06-09 17:13:54.475424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd8c8ee9c343'
down_revision: Union[str, None] = '4a92f3cde7d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the old and new enum types
old_notification_types = (
    'GROUP_INVITE', 
    'NEW_BILL', 
    'BILL_UPDATE', 
    'MEMBER_ADDED_TO_GROUP'
)
new_notification_types = (
    'GROUP_INVITE', 
    'NEW_BILL', 
    'BILL_UPDATE', 
    'MEMBER_ADDED_TO_GROUP', 
    'FRIEND_REQUEST',
    'FRIEND_REQUEST_ACCEPTED',
    'BILL_PAYMENT_REMINDER',
    'TRANSACTION_REMINDER'
)

old_enum = sa.Enum(*old_notification_types, name='notificationtype')
new_enum = sa.Enum(*new_notification_types, name='notificationtype')


def upgrade() -> None:
    """Upgrade schema to include new notification types."""
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.alter_column(
            'notification_type',
            existing_type=old_enum,
            type_=new_enum,
            existing_nullable=True
        )


def downgrade() -> None:
    """Downgrade schema to remove new notification types."""
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.alter_column(
            'notification_type',
            existing_type=new_enum,
            type_=old_enum,
            existing_nullable=True
        )
