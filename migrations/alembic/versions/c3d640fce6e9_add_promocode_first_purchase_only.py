"""Add first_purchase_only field to promocodes table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-07 12:00:00.000000

This migration adds the first_purchase_only field to the promocodes table.
This field indicates whether a promocode can only be used for a user's first purchase.

The field defaults to False for backward compatibility with existing promocodes.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d640fce6e9"
down_revision: Union[str, None] = "d7f6e838328b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add first_purchase_only column to promocodes table."""
    op.add_column(
        "promocodes",
        sa.Column("first_purchase_only", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Remove first_purchase_only column from promocodes table."""
    op.drop_column("promocodes", "first_purchase_only")
