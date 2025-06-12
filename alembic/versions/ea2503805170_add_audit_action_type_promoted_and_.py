"""add audit action type: promoted and demoted role

Revision ID: ea2503805170
Revises: dd8c8ee9c343
Create Date: 2025-06-09 20:20:03.329350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea2503805170'
down_revision: Union[str, None] = 'dd8c8ee9c343'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

old_audit_action_types = (
    "bill_created",
    "bill_updated",
    "bill_deleted",
    "payment_created",
    "payment_updated",
    "payment_deleted",
    "member_invited",
    "member_added",
    "member_left",
    "member_removed",
    "member_role_updated",
    "group_created",
    "group_details_updated",
)

new_audit_action_types = (
    "bill_created",
    "bill_updated",
    "bill_deleted",
    "payment_created",
    "payment_updated",
    "payment_deleted",
    "member_invited",
    "member_added",
    "member_left",
    "member_removed",
    "member_role_promoted",
    "member_role_demoted",
    "group_created",
    "group_details_updated",
)


old_enum = sa.Enum(*old_audit_action_types, name="auditactiontype")
new_enum = sa.Enum(*new_audit_action_types, name="auditactiontype")


def upgrade() -> None:
    with op.batch_alter_table("audit_log_entries") as batch_op:
        batch_op.alter_column(
            "action_type",
            existing_type=old_enum,
            type_=new_enum,
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_log_entries") as batch_op:
        batch_op.alter_column(
            "action_type",
            existing_type=new_enum,
            type_=old_enum,
            existing_nullable=False,
        )
