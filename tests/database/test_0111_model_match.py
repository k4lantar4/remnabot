"""M4-T4: 4.2 models match Alembic 0111 identity + boot extras.

Full ``alembic revision --autogenerate`` against a remnabot-lineage restore
is expected to still propose deferred 4.2 tables and to ignore unmapped
production columns (C2C / wholesale / user_disabled). Those are M4-T7, not
a new revision. This module locks the 0111-owned mapping so it cannot drift.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, Text

from app.database.models import PaymentMethodConfig, PromoCode, Subscription, Tariff, User

_0111_SUB_INDEXES = {
    'uq_subscriptions_remnawave_id',
    'ix_subscriptions_remnawave_short_uuid',
    'ix_subscriptions_grace_candidate',
    'ix_subscriptions_grace_expiry_scan',
}


def _column(table, name):
    return table.__table__.c[name]


def _index_by_name(table, name):
    for index in table.__table__.indexes:
        if index.name == name:
            return index
    raise AssertionError(f'{table.__tablename__} missing index {name}')


def test_user_remnawave_id_is_unique_indexed_bigint() -> None:
    column = _column(User, 'remnawave_id')
    assert isinstance(column.type, BigInteger)
    assert column.nullable is True
    assert column.unique is True
    assert column.index is True
    index = _index_by_name(User, 'ix_users_remnawave_id')
    assert index.unique is True
    assert [col.name for col in index.columns] == ['remnawave_id']


def test_subscription_remnawave_id_is_plain_with_partial_unique() -> None:
    column = _column(Subscription, 'remnawave_id')
    assert isinstance(column.type, BigInteger)
    assert column.nullable is True
    assert not column.unique
    assert not column.index
    index = _index_by_name(Subscription, 'uq_subscriptions_remnawave_id')
    assert index.unique is True
    assert [col.name for col in index.columns] == ['remnawave_id']
    where = {key: str(value) for key, value in index.dialect_kwargs.items()}
    assert where['postgresql_where'] == 'remnawave_id IS NOT NULL'
    assert where['sqlite_where'] == 'remnawave_id IS NOT NULL'


def test_0111_boot_extras_are_mapped() -> None:
    assert isinstance(_column(User, 'referral_days_subscription_id').type, Integer)
    assert _column(User, 'referral_days_subscription_id').nullable is True
    pref = _column(User, 'referral_reward_preference')
    assert isinstance(pref.type, String)
    assert pref.nullable is True
    assert pref.type.length == 10

    for name in ('grace_candidate_reason', 'grace_candidate_at', 'grace_suppressed_until'):
        assert _column(Subscription, name).nullable is True
    assert _column(Subscription, 'grace_candidate_reason').type.length == 16

    assert isinstance(_column(PaymentMethodConfig, 'description').type, Text)
    assert _column(PaymentMethodConfig, 'description').nullable is True

    lava = _column(Tariff, 'lava_product_id')
    assert isinstance(lava.type, String)
    assert lava.nullable is True
    assert lava.type.length == 255

    traffic = _column(PromoCode, 'traffic_gb')
    assert isinstance(traffic.type, Integer)
    assert traffic.nullable is False
    assert str(traffic.server_default.arg) == '0'

    names = {index.name for index in Subscription.__table__.indexes}
    assert _0111_SUB_INDEXES <= names
