"""add quick_amounts to payment_method_configs (upstream 0090 rechain)

Revision ID: 0097
Revises: 0096
Create Date: 2026-06-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0097'
down_revision: Union[str, None] = '0096'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind: sa.engine.Connection, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    return any(col['name'] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, 'payment_method_configs', 'quick_amounts'):
        op.add_column('payment_method_configs', sa.Column('quick_amounts', sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, 'payment_method_configs', 'quick_amounts'):
        op.drop_column('payment_method_configs', 'quick_amounts')
