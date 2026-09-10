"""0112: referral_earnings reward columns required by 4.2 ORM on /start

M6-T5: ``get_main_menu_keyboard_async`` (MENU_LAYOUT_ENABLED) calls
``get_user_referral_stats`` which ``SUM(referral_earnings.days_granted)``.
Grafted remnabot-lineage ``0111`` does not have those 4.2 columns, so /start
aborts the SQL transaction (UndefinedColumnError → InFailedSQLTransaction).

Upstream 0108 added the same columns on a different graph (revises 0107). This
revision revises grafted ``0111`` and does not reuse donor revision id 0108.

Does NOT create deferred ``referral_reward_levels`` (M4-T1 product-deferred).

Revision ID: 0112
Revises: 0111
Create Date: 2026-09-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0112'
down_revision: Union[str, None] = '0111'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EARNING_COLUMNS = (
    ('reward_type', sa.Column('reward_type', sa.String(length=10), nullable=False, server_default='money')),
    ('level', sa.Column('level', sa.Integer(), nullable=False, server_default='1')),
    ('days_granted', sa.Column('days_granted', sa.Integer(), nullable=False, server_default='0')),
    ('tariff_id', sa.Column('tariff_id', sa.Integer(), nullable=True)),
)
_EARNING_TARIFF_FK = 'fk_referral_earnings_tariff_id'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'referral_earnings' not in tables:
        return

    existing_cols = {col['name'] for col in inspector.get_columns('referral_earnings')}
    added: list[str] = []
    for name, column in _EARNING_COLUMNS:
        if name not in existing_cols:
            op.add_column('referral_earnings', column)
            added.append(name)

    inspector = sa.inspect(bind)
    tariff_fk_exists = any(
        'tariff_id' in (fk.get('constrained_columns') or []) for fk in inspector.get_foreign_keys('referral_earnings')
    )
    tariff_column_present = 'tariff_id' in existing_cols | set(added)
    if tariff_column_present and not tariff_fk_exists and bind.dialect.name != 'sqlite':
        op.create_foreign_key(
            _EARNING_TARIFF_FK,
            'referral_earnings',
            'tariffs',
            ['tariff_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'referral_earnings' not in tables:
        return

    existing_fks = {fk['name'] for fk in inspector.get_foreign_keys('referral_earnings')}
    if _EARNING_TARIFF_FK in existing_fks and bind.dialect.name != 'sqlite':
        op.drop_constraint(_EARNING_TARIFF_FK, 'referral_earnings', type_='foreignkey')

    existing_cols = {col['name'] for col in inspector.get_columns('referral_earnings')}
    for name, _column in reversed(_EARNING_COLUMNS):
        if name in existing_cols:
            op.drop_column('referral_earnings', name)
