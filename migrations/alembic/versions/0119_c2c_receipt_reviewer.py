"""c2c receipts: record which user reviewed a receipt and through which channel

``reviewed_by_telegram_id`` is empty when an email-only admin decides a receipt in the cabinet, so
the cabinet review screen could not name the reviewer. Two additive, nullable columns:
``reviewed_by_user_id`` (FK to ``users.id``) and ``reviewed_via`` (``'bot'`` or ``'cabinet'``).
Existing rows stay valid with both NULL.

Idempotent by inspector guard.

Revision ID: 0119
Revises: 0118
Create Date: 2026-09-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0119'
down_revision: Union[str, None] = '0118'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'c2c_receipts'
FK_NAME = 'fk_c2c_receipts_reviewed_by_user_id_users'


def _has_column(column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col['name'] == column for col in inspector.get_columns(TABLE))


def upgrade() -> None:
    if not _has_column('reviewed_by_user_id'):
        op.add_column(TABLE, sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True))
        op.create_foreign_key(FK_NAME, TABLE, 'users', ['reviewed_by_user_id'], ['id'], ondelete='SET NULL')

    if not _has_column('reviewed_via'):
        op.add_column(TABLE, sa.Column('reviewed_via', sa.String(length=16), nullable=True))


def downgrade() -> None:
    if _has_column('reviewed_via'):
        op.drop_column(TABLE, 'reviewed_via')

    if _has_column('reviewed_by_user_id'):
        inspector = sa.inspect(op.get_bind())
        if any(fk.get('name') == FK_NAME for fk in inspector.get_foreign_keys(TABLE)):
            op.drop_constraint(FK_NAME, TABLE, type_='foreignkey')
        op.drop_column(TABLE, 'reviewed_by_user_id')
