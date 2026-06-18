"""c2c_receipts approved_amount and rejection_reason_key

Revision ID: 0094
Revises: 0093
Create Date: 2026-06-18

Track A: C2C admin inbox — custom approve amount and structured reject metadata.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0094'
down_revision: Union[str, None] = '0093'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column in [c['name'] for c in inspector.get_columns(table)]


def upgrade() -> None:
    if not _has_column('c2c_receipts', 'approved_amount_kopeks'):
        op.add_column('c2c_receipts', sa.Column('approved_amount_kopeks', sa.Integer(), nullable=True))
    if not _has_column('c2c_receipts', 'rejection_reason_key'):
        op.add_column('c2c_receipts', sa.Column('rejection_reason_key', sa.String(32), nullable=True))


def downgrade() -> None:
    if _has_column('c2c_receipts', 'rejection_reason_key'):
        op.drop_column('c2c_receipts', 'rejection_reason_key')
    if _has_column('c2c_receipts', 'approved_amount_kopeks'):
        op.drop_column('c2c_receipts', 'approved_amount_kopeks')
