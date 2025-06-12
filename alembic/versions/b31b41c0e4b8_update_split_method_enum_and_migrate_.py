"""Update split_method enum and migrate bill data

Revision ID: b31b41c0e4b8
Revises: dca373bd571e
Create Date: 2024-03-29 16:53:23.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b31b41c0e4b8'
down_revision: Union[str, None] = 'dca373bd571e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration is specific to MySQL syntax for modifying ENUMs.
    # Step 1: Add 'exact' to the list of possible ENUM values.
    op.execute("ALTER TABLE bills MODIFY COLUMN split_method ENUM('equal', 'percentage', 'item', 'exact') NOT NULL")

    # Step 2: Now that 'exact' is a valid option, update the data.
    op.execute("UPDATE bills SET split_method = 'exact' WHERE split_method = 'percentage'")

    # Step 3: Remove 'percentage' from the list of ENUM values, leaving the final desired state.
    op.execute("ALTER TABLE bills MODIFY COLUMN split_method ENUM('equal', 'item', 'exact') NOT NULL")


def downgrade() -> None:
    # This migration is specific to MySQL syntax for modifying ENUMs.
    # Step 1: Add 'percentage' back to the list of ENUM values to allow for data rollback.
    op.execute("ALTER TABLE bills MODIFY COLUMN split_method ENUM('equal', 'item', 'exact', 'percentage') NOT NULL")
    
    # Step 2: Now that 'percentage' is a valid option, change the data back.
    op.execute("UPDATE bills SET split_method = 'percentage' WHERE split_method = 'exact'")

    # Step 3: Remove 'exact' to revert to the original ENUM state.
    op.execute("ALTER TABLE bills MODIFY COLUMN split_method ENUM('equal', 'percentage', 'item') NOT NULL")
