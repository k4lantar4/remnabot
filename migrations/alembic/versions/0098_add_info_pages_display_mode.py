"""add info_pages display_mode (upstream 0091 rechain)

Revision ID: 0098
Revises: 0097
Create Date: 2026-06-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0098'
down_revision: Union[str, None] = '0097'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind: sa.engine.Connection, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    return any(col['name'] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, 'info_pages', 'display_mode'):
        op.add_column(
            'info_pages',
            sa.Column('display_mode', sa.String(length=10), nullable=False, server_default='both'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, 'info_pages', 'display_mode'):
        op.drop_column('info_pages', 'display_mode')
