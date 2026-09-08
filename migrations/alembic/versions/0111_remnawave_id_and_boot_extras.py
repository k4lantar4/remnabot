"""0111: remnawave_id (M3-ID) + mapped extras required to boot 4.2 on remnabot schema

Remnawave 3.4.3 dropped ``users.uuid``; panel identity is numeric ``users.id``
(former 2.8.1 ``t_id``). This revision adds nullable BIGINT ``remnawave_id`` on
bot ``users`` (full unique) and ``subscriptions`` (partial unique where NOT
NULL), plus a non-unique index on existing ``remnawave_short_uuid``.

M4-T1 proved 4.2 ORM also SELECTs mapped columns that are absent on remnabot
0104. Those extras are schema-only in this same revision (no 0112):
referral choice columns, grace *markers* on subscriptions, payment method
description, tariffs.lava_product_id, promocodes.traffic_gb.

Does NOT create deferred tables (cispay/platega/lava/coupons/legal/grace
sessions). ``grace_access_sessions`` is inspector-guarded only if already
present. Custom remnabot columns (c2c, wholesale, user_disabled) are not
dropped.

Revision ID: 0111
Revises: 0104
Create Date: 2026-09-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0111'
down_revision: Union[str, None] = '0104'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SUBSCRIPTION_ID_NOT_NULL = 'remnawave_id IS NOT NULL'


def _columns(inspector: sa.Inspector, table: str) -> dict[str, dict]:
    return {column['name']: column for column in inspector.get_columns(table)}


def _index_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {str(item['name']) for item in inspector.get_indexes(table) if item.get('name')}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'users' in tables:
        user_cols = _columns(inspector, 'users')
        if 'remnawave_id' not in user_cols:
            op.add_column('users', sa.Column('remnawave_id', sa.BigInteger(), nullable=True))
        if 'referral_days_subscription_id' not in user_cols:
            op.add_column('users', sa.Column('referral_days_subscription_id', sa.Integer(), nullable=True))
        if 'referral_reward_preference' not in user_cols:
            op.add_column('users', sa.Column('referral_reward_preference', sa.String(length=10), nullable=True))
        inspector = sa.inspect(bind)
        if 'ix_users_remnawave_id' not in _index_names(inspector, 'users'):
            op.create_index('ix_users_remnawave_id', 'users', ['remnawave_id'], unique=True)

    if 'subscriptions' in tables:
        inspector = sa.inspect(bind)
        sub_cols = _columns(inspector, 'subscriptions')
        if 'remnawave_id' not in sub_cols:
            op.add_column('subscriptions', sa.Column('remnawave_id', sa.BigInteger(), nullable=True))
        if 'grace_candidate_reason' not in sub_cols:
            op.add_column('subscriptions', sa.Column('grace_candidate_reason', sa.String(length=16), nullable=True))
        if 'grace_candidate_at' not in sub_cols:
            op.add_column('subscriptions', sa.Column('grace_candidate_at', sa.DateTime(timezone=True), nullable=True))
        if 'grace_suppressed_until' not in sub_cols:
            op.add_column('subscriptions', sa.Column('grace_suppressed_until', sa.DateTime(timezone=True), nullable=True))

        inspector = sa.inspect(bind)
        subscription_indexes = _index_names(inspector, 'subscriptions')
        if 'uq_subscriptions_remnawave_id' not in subscription_indexes:
            op.create_index(
                'uq_subscriptions_remnawave_id',
                'subscriptions',
                ['remnawave_id'],
                unique=True,
                postgresql_where=sa.text(_SUBSCRIPTION_ID_NOT_NULL),
                sqlite_where=sa.text(_SUBSCRIPTION_ID_NOT_NULL),
            )
        if 'ix_subscriptions_remnawave_short_uuid' not in subscription_indexes:
            op.create_index(
                'ix_subscriptions_remnawave_short_uuid',
                'subscriptions',
                ['remnawave_short_uuid'],
                unique=False,
            )
        if 'ix_subscriptions_grace_candidate' not in subscription_indexes:
            op.create_index(
                'ix_subscriptions_grace_candidate',
                'subscriptions',
                ['grace_candidate_at', 'grace_candidate_reason'],
                unique=False,
            )
        if (
            'ix_subscriptions_grace_expiry_scan' not in subscription_indexes
            and {'status', 'is_trial', 'end_date'} <= set(sub_cols)
        ):
            op.create_index(
                'ix_subscriptions_grace_expiry_scan',
                'subscriptions',
                ['status', 'is_trial', 'end_date'],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if 'payment_method_configs' in inspector.get_table_names():
        if 'description' not in _columns(inspector, 'payment_method_configs'):
            op.add_column('payment_method_configs', sa.Column('description', sa.Text(), nullable=True))

    inspector = sa.inspect(bind)
    if 'tariffs' in inspector.get_table_names():
        if 'lava_product_id' not in _columns(inspector, 'tariffs'):
            op.add_column('tariffs', sa.Column('lava_product_id', sa.String(length=255), nullable=True))

    inspector = sa.inspect(bind)
    if 'promocodes' in inspector.get_table_names():
        if 'traffic_gb' not in _columns(inspector, 'promocodes'):
            op.add_column(
                'promocodes',
                sa.Column('traffic_gb', sa.Integer(), nullable=False, server_default='0'),
            )

    inspector = sa.inspect(bind)
    if 'grace_access_sessions' in inspector.get_table_names():
        grace_columns = _columns(inspector, 'grace_access_sessions')
        if 'remnawave_id' not in grace_columns:
            op.add_column('grace_access_sessions', sa.Column('remnawave_id', sa.BigInteger(), nullable=True))
        if grace_columns.get('remnawave_uuid', {}).get('nullable') is False:
            with op.batch_alter_table('grace_access_sessions') as batch:
                batch.alter_column(
                    'remnawave_uuid',
                    existing_type=sa.String(length=255),
                    nullable=True,
                )
        inspector = sa.inspect(bind)
        if 'ix_grace_access_sessions_remnawave_id' not in _index_names(inspector, 'grace_access_sessions'):
            op.create_index(
                'ix_grace_access_sessions_remnawave_id',
                'grace_access_sessions',
                ['remnawave_id'],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'grace_access_sessions' in inspector.get_table_names():
        grace_indexes = _index_names(inspector, 'grace_access_sessions')
        if 'ix_grace_access_sessions_remnawave_id' in grace_indexes:
            op.drop_index('ix_grace_access_sessions_remnawave_id', table_name='grace_access_sessions')
        inspector = sa.inspect(bind)
        if 'remnawave_id' in _columns(inspector, 'grace_access_sessions'):
            op.drop_column('grace_access_sessions', 'remnawave_id')

    inspector = sa.inspect(bind)
    if 'promocodes' in inspector.get_table_names() and 'traffic_gb' in _columns(inspector, 'promocodes'):
        op.drop_column('promocodes', 'traffic_gb')

    inspector = sa.inspect(bind)
    if 'tariffs' in inspector.get_table_names() and 'lava_product_id' in _columns(inspector, 'tariffs'):
        op.drop_column('tariffs', 'lava_product_id')

    inspector = sa.inspect(bind)
    if 'payment_method_configs' in inspector.get_table_names():
        if 'description' in _columns(inspector, 'payment_method_configs'):
            op.drop_column('payment_method_configs', 'description')

    inspector = sa.inspect(bind)
    if 'subscriptions' in inspector.get_table_names():
        subscription_indexes = _index_names(inspector, 'subscriptions')
        for index_name in (
            'ix_subscriptions_grace_expiry_scan',
            'ix_subscriptions_grace_candidate',
            'ix_subscriptions_remnawave_short_uuid',
            'uq_subscriptions_remnawave_id',
        ):
            if index_name in subscription_indexes:
                op.drop_index(index_name, table_name='subscriptions')
        inspector = sa.inspect(bind)
        sub_cols = _columns(inspector, 'subscriptions')
        for column_name in (
            'grace_suppressed_until',
            'grace_candidate_at',
            'grace_candidate_reason',
            'remnawave_id',
        ):
            if column_name in sub_cols:
                op.drop_column('subscriptions', column_name)

    inspector = sa.inspect(bind)
    if 'users' in inspector.get_table_names():
        if 'ix_users_remnawave_id' in _index_names(inspector, 'users'):
            op.drop_index('ix_users_remnawave_id', table_name='users')
        inspector = sa.inspect(bind)
        user_cols = _columns(inspector, 'users')
        for column_name in (
            'referral_reward_preference',
            'referral_days_subscription_id',
            'remnawave_id',
        ):
            if column_name in user_cols:
                op.drop_column('users', column_name)
