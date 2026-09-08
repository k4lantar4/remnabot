"""multi account per user — drop one-sub-per-tariff index, add account_sequence

Revision ID: 0091
Revises: 0090
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0091'
down_revision: Union[str, None] = '0090'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('uq_subscriptions_user_tariff_active', table_name='subscriptions')
    op.add_column(
        'subscriptions',
        sa.Column('account_sequence', sa.Integer(), nullable=False, server_default='1'),
    )
    op.execute(
        sa.text("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS seq
            FROM subscriptions
        )
        UPDATE subscriptions s SET account_sequence = ranked.seq
        FROM ranked WHERE s.id = ranked.id
    """)
    )
    op.alter_column('subscriptions', 'account_sequence', server_default=None)


def downgrade() -> None:
    op.drop_column('subscriptions', 'account_sequence')
    op.execute(
        sa.text("""
        CREATE UNIQUE INDEX uq_subscriptions_user_tariff_active
        ON subscriptions (user_id, tariff_id)
        WHERE tariff_id IS NOT NULL AND status IN ('active', 'trial', 'limited')
    """)
    )
