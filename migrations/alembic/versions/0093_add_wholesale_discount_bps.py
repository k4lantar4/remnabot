"""add wholesale_discount_bps and business_role to users

Revision ID: 0093
Revises: 0092
Create Date: 2026-06-15

DB-driven partner wholesale pricing (integer basis points).
wholesale_discount_bps: 2500 = 25% off catalog subtotal for approved partners.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0093'
down_revision: Union[str, None] = '0092'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column in [c['name'] for c in inspector.get_columns(table)]


def upgrade() -> None:
    if not _has_column('users', 'business_role'):
        op.add_column(
            'users',
            sa.Column('business_role', sa.String(length=20), nullable=False, server_default='customer'),
        )
        op.create_index('ix_users_business_role', 'users', ['business_role'])

    if not _has_column('users', 'wholesale_discount_bps'):
        op.add_column(
            'users',
            sa.Column('wholesale_discount_bps', sa.Integer(), nullable=False, server_default='0'),
        )

    # Backfill approved partners: role + default 50% wholesale (5000 BPS).
    op.execute(
        sa.text(
            "UPDATE users SET business_role = 'partner', wholesale_discount_bps = 5000 "
            "WHERE partner_status = 'approved' AND business_role = 'customer'"
        )
    )


def downgrade() -> None:
    if _has_column('users', 'wholesale_discount_bps'):
        op.drop_column('users', 'wholesale_discount_bps')

    if _has_column('users', 'business_role'):
        op.drop_index('ix_users_business_role', table_name='users')
        op.drop_column('users', 'business_role')
