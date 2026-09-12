"""0118: create the upstream tables our lineage deferred at the 0095 fork

At 0095 our Alembic chain forked from upstream's under the same numbers (ours
``0095_partner_panel_fields`` … ``0117_guest_purchase_campaign_and_idempotency``). Upstream's
``0095_add_coupons``, ``0099_add_platega_subscriptions``, ``0100_platega_sub_unique_alive``,
``0102_coupon_max_per_user`` and the deferred-gateway revisions were archived rather than grafted
— but their models and the code reading them came in with every upstream sync. Only databases
built by ``Base.metadata.create_all`` ever had the tables, so on a migrated database:

  * ``GET /cabinet/admin/payments`` → 500, ``relation "cispay_payments" does not exist``
    (``payment_verification_service.list_recent_pending_payments`` queries every gateway);
  * ``GET /cabinet/admin/users/{id}/activity`` → 500 for every user, ``relation "coupons"``
    (the ``coupon`` source in ``_activity_sources``);
  * ``subscription_dedup_service`` logs ``relation "platega_subscriptions" does not exist`` on
    startup, poisoning the transaction it runs in.

The column half of the same fork — ``guest_purchases.campaign_slug`` / ``idempotency_key``,
upstream's archived ``0106``/``0107`` — is revision ``0117``, which landed while this one was in
review. Nothing to repeat here.

Creating a deferred gateway's table is **not** enabling it: CisPay, Platega and Lava stay off by
their ``*_ENABLED`` flags (workspace policy: disabled gateways are never deleted, never enabled).
The schema exists only so a shared query stops raising ``UndefinedTable``.

Deliberately NOT here: ``referral_reward_levels``, deferred by product decision M4-T1 and guarded
by ``tests/database/test_0111_remnawave_id.py::FORBIDDEN_TABLES``.

Idempotent by inspector guard: a no-op on a fresh database that ``create_all`` already populated,
and safe to re-run on a partially migrated one.

Revision ID: 0118
Revises: 0117
Create Date: 2026-09-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0118'
down_revision: Union[str, None] = '0117'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Statuses that count as a live recurring binding (upstream ``0100``): at most one per
#: subscription, so a racing "enable" loses on the index and reuses the winner's row.
_ALIVE_STATES_SQL = "status IN ('PENDING', 'ACTIVE', 'PAST_DUE')"

#: Dropped by ``downgrade`` in reverse order — ``coupons`` before the batches it references.
_TABLES_IN_CREATE_ORDER = (
    'cispay_payments',
    'platega_subscriptions',
    'lava_subscriptions',
    'recurrent_payments',
    'coupon_batches',
    'coupons',
    'legal_consents',
)


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _create_cispay_payments() -> None:
    op.create_table(
        'cispay_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.String(length=64), nullable=False),
        sa.Column('cispay_payment_id', sa.String(length=64), nullable=True),
        sa.Column('amount_kopeks', sa.Integer(), nullable=False),
        # What the buyer is charged — may include the fee when the buyer pays it.
        sa.Column('charged_amount_kopeks', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('is_paid', sa.Boolean(), nullable=True),
        sa.Column('payment_url', sa.Text(), nullable=True),
        sa.Column('payment_method', sa.String(length=32), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('callback_payload', sa.JSON(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cispay_payments_id', 'cispay_payments', ['id'], unique=False)
    op.create_index('ix_cispay_payments_user_id', 'cispay_payments', ['user_id'], unique=False)
    op.create_index('ix_cispay_payments_order_id', 'cispay_payments', ['order_id'], unique=True)
    op.create_index('ix_cispay_payments_cispay_payment_id', 'cispay_payments', ['cispay_payment_id'], unique=True)


def _create_platega_subscriptions() -> None:
    op.create_table(
        'platega_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=False),
        sa.Column('tariff_id', sa.Integer(), nullable=True),
        sa.Column('platega_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('interval', sa.Integer(), nullable=False),
        sa.Column('charge_days', sa.Integer(), nullable=False),
        sa.Column('amount_kopeks', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('redirect_url', sa.Text(), nullable=True),
        sa.Column('next_charge_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_charge_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_charge_external_id', sa.String(length=255), nullable=True),
        sa.Column('charges_success', sa.Integer(), nullable=False),
        sa.Column('charges_failed', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tariff_id'], ['tariffs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_platega_subscriptions_id', 'platega_subscriptions', ['id'], unique=False)
    op.create_index('ix_platega_subscriptions_user_id', 'platega_subscriptions', ['user_id'], unique=False)
    op.create_index(
        'ix_platega_subscriptions_subscription_id', 'platega_subscriptions', ['subscription_id'], unique=False
    )
    op.create_index(
        'ix_platega_subscriptions_platega_subscription_id',
        'platega_subscriptions',
        ['platega_subscription_id'],
        unique=True,
    )
    op.create_index(
        'ix_platega_subscriptions_user_active', 'platega_subscriptions', ['user_id', 'status'], unique=False
    )
    op.create_index(
        'uq_platega_subscriptions_alive',
        'platega_subscriptions',
        ['subscription_id'],
        unique=True,
        postgresql_where=sa.text(_ALIVE_STATES_SQL),
        sqlite_where=sa.text(_ALIVE_STATES_SQL),
    )


def _create_lava_subscriptions() -> None:
    op.create_table(
        'lava_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=False),
        sa.Column('tariff_id', sa.Integer(), nullable=True),
        sa.Column('lava_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('lava_product_id', sa.String(length=255), nullable=False),
        sa.Column('lava_consumer_id', sa.String(length=255), nullable=True),
        # The subscription's orderId: how the webhook tells a recurring charge from an invoice.
        sa.Column('order_id', sa.String(length=255), nullable=False),
        sa.Column('charge_days', sa.Integer(), nullable=False),
        sa.Column('amount_kopeks', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('redirect_url', sa.Text(), nullable=True),
        sa.Column('next_charge_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_charge_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_charge_external_id', sa.String(length=255), nullable=True),
        sa.Column('charges_success', sa.Integer(), nullable=False),
        sa.Column('charges_failed', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tariff_id'], ['tariffs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lava_subscriptions_id', 'lava_subscriptions', ['id'], unique=False)
    op.create_index('ix_lava_subscriptions_user_id', 'lava_subscriptions', ['user_id'], unique=False)
    op.create_index('ix_lava_subscriptions_subscription_id', 'lava_subscriptions', ['subscription_id'], unique=False)
    op.create_index(
        'ix_lava_subscriptions_lava_subscription_id', 'lava_subscriptions', ['lava_subscription_id'], unique=True
    )
    op.create_index('ix_lava_subscriptions_order_id', 'lava_subscriptions', ['order_id'], unique=True)
    op.create_index('ix_lava_subscriptions_user_active', 'lava_subscriptions', ['user_id', 'status'], unique=False)
    op.create_index(
        'uq_lava_subscriptions_alive',
        'lava_subscriptions',
        ['subscription_id'],
        unique=True,
        postgresql_where=sa.text(_ALIVE_STATES_SQL),
        sqlite_where=sa.text(_ALIVE_STATES_SQL),
    )


def _create_recurrent_payments() -> None:
    op.create_table(
        'recurrent_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('language'),
    )
    op.create_index('ix_recurrent_payments_id', 'recurrent_payments', ['id'], unique=False)


def _create_coupon_batches() -> None:
    op.create_table(
        'coupon_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('tariff_id', sa.Integer(), nullable=True),
        sa.Column('period_days', sa.Integer(), nullable=False),
        sa.Column('coupons_total', sa.Integer(), nullable=False),
        # Bookkeeping only: the partner settles the wholesale price outside the bot.
        sa.Column('wholesale_price_kopeks', sa.Integer(), nullable=False),
        sa.Column('max_per_user', sa.Integer(), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_revoked', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['tariff_id'], ['tariffs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_coupon_batches_id', 'coupon_batches', ['id'], unique=False)
    op.create_index('ix_coupon_batches_tariff_id', 'coupon_batches', ['tariff_id'], unique=False)


def _create_coupons() -> None:
    op.create_table(
        'coupons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('redeemed_by', sa.Integer(), nullable=True),
        sa.Column('redeemed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['coupon_batches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['redeemed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_coupons_id', 'coupons', ['id'], unique=False)
    op.create_index('ix_coupons_token', 'coupons', ['token'], unique=True)
    op.create_index('ix_coupons_redeemed_by', 'coupons', ['redeemed_by'], unique=False)
    op.create_index('ix_coupons_batch_status', 'coupons', ['batch_id', 'status'], unique=False)


def _create_legal_consents() -> None:
    op.create_table(
        'legal_consents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('document', sa.String(length=32), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=False),
        # Where the checkbox was ticked: cabinet_telegram / cabinet_email / …
        sa.Column('source', sa.String(length=32), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_legal_consents_id', 'legal_consents', ['id'], unique=False)
    # Append-only journal, no uniqueness: re-consent after a new document revision must land
    # next to the old row, not replace it.
    op.create_index('ix_legal_consents_user_document', 'legal_consents', ['user_id', 'document'], unique=False)


_CREATORS = {
    'cispay_payments': _create_cispay_payments,
    'platega_subscriptions': _create_platega_subscriptions,
    'lava_subscriptions': _create_lava_subscriptions,
    'recurrent_payments': _create_recurrent_payments,
    'coupon_batches': _create_coupon_batches,
    'coupons': _create_coupons,
    'legal_consents': _create_legal_consents,
}


def upgrade() -> None:
    existing = _table_names(sa.inspect(op.get_bind()))

    for table in _TABLES_IN_CREATE_ORDER:
        if table not in existing:
            _CREATORS[table]()


def downgrade() -> None:
    existing = _table_names(sa.inspect(op.get_bind()))

    for table in reversed(_TABLES_IN_CREATE_ORDER):
        if table in existing:
            op.drop_table(table)
