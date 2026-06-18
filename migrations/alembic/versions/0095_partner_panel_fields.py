"""partner panel fields: purchase_note + panel_brand_prefix

Revision ID: 0095
Revises: 0094
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0095'
down_revision: Union[str, None] = '0094'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column in [c['name'] for c in inspector.get_columns(table)]


def upgrade() -> None:
    if not _has_column('subscriptions', 'purchase_note'):
        op.add_column('subscriptions', sa.Column('purchase_note', sa.Text(), nullable=True))

    if not _has_column('users', 'panel_brand_prefix'):
        op.add_column('users', sa.Column('panel_brand_prefix', sa.String(length=24), nullable=True))


def downgrade() -> None:
    if _has_column('users', 'panel_brand_prefix'):
        op.drop_column('users', 'panel_brand_prefix')

    if _has_column('subscriptions', 'purchase_note'):
        op.drop_column('subscriptions', 'purchase_note')
