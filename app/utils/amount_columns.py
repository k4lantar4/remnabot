"""Every money column in the schema, classified by the scale its integer is stored on.

Background: balances are stored in Toman 1:1 ("Phase B") while catalog prices are still stored
x100 (`price_kopeks`). Toman Phase C moves the catalog columns to Toman 1:1 as well, in Alembic
revision ``0113``, after which the whole database is on one scale.

This module is the single source of truth for that migration and for the guard test in
``tests/utils/test_amount_columns.py``: the test fails when a money column exists in
``app.database.models`` that is not listed here, so a new (or newly merged upstream) money column
cannot silently pick the wrong scale. It replaces the hand-maintained
``price_display._BALANCE_SCALE_TRANSACTION_TYPES`` as the thing a human has to keep honest — the
difference being that CI now checks it.

Nothing here converts anything; it only classifies.
"""

import re
from typing import Literal, NamedTuple


AmountColumnKind = Literal['int', 'json_values']

#: Bookkeeping tables of the Phase C scale change. ``0114`` creates them (structural, safe on its
#: own); ``0115`` fills them together with the code that reads Toman. **The tables existing means
#: nothing** — only a ``TOMAN_SCALE`` row in ``amount_scale_state`` declares the stored amounts to be
#: Toman 1:1.
AMOUNT_SCALE_STATE_TABLE = 'amount_scale_state'
AMOUNT_SCALE_ROUNDING_LOG_TABLE = 'amount_scale_rounding_log'
TOMAN_SCALE = 'toman'

#: Column names that look like money and therefore must be classified below.
#: ``packages`` is here because ``tariffs.traffic_topup_packages`` is a ``{gb: price}`` map whose
#: name says nothing about money — it slipped past ``0115`` for exactly that reason and kept
#: charging 100x until ``0116`` (see that revision).
MONEY_COLUMN_NAME_PATTERN = re.compile(r'kopeks|price|amount|packages', re.IGNORECASE)


class ColumnRef(NamedTuple):
    """One money column.

    ``kind='json_values'`` means the JSON payload is a mapping/list whose *values* are the amounts
    (``tariffs.period_prices``, ``payment_method_configs.quick_amounts``).

    ``where`` is a SQL predicate naming the subset of rows that sit on this scale, for the two
    columns that are mixed-scale per row type. ``None`` means the whole column.
    """

    table: str
    column: str
    kind: AmountColumnKind = 'int'
    where: str | None = None
    note: str = ''


#: ``transactions.type`` values whose ``amount_kopeks`` was a catalog amount (x100) before revision
#: ``0115`` divided it. Together with :data:`PRE_PHASE_C_TOMAN_TRANSACTION_TYPES` these must cover
#: every ``TransactionType`` — asserted by the guard test, so a type added upstream cannot quietly
#: go unclassified.
#:
#: This is migration metadata, not a runtime scale decision: after ``0115`` every row is Toman and
#: nothing in the application asks which set a type belongs to. It stays here because ``0115``'s
#: ``where`` clauses are built from it and its ``downgrade()`` needs the same split.
CATALOG_SCALE_TRANSACTION_TYPES: frozenset[str] = frozenset({'subscription_payment', 'gift_payment'})

#: The complement: types already stored Toman 1:1 before Phase C, which ``0115`` must not touch.
PRE_PHASE_C_TOMAN_TRANSACTION_TYPES: frozenset[str] = frozenset(
    {
        'deposit',
        'withdrawal',
        'refund',
        'failed_refund',
        'referral_reward',
        'poll_reward',
    }
)

#: ``subscription_events.event_type`` values whose ``amount_kopeks`` is a catalog amount.
#: ``balance_topup`` (mirrors a deposit), ``promocode_activation`` and ``campaign_registration``
#: (balance bonuses) are Toman already; the remaining event types carry no amount. An unknown
#: event type — the web API lets an external dashboard post one — is deliberately left untouched.
CATALOG_SCALE_SUBSCRIPTION_EVENT_TYPES: frozenset[str] = frozenset({'purchase', 'renewal', 'activation'})


#: Catalog scale (x100) today — revision ``0113`` divides these by 100.
CATALOG_SCALE_COLUMNS: tuple[ColumnRef, ...] = (
    ColumnRef('coupon_batches', 'wholesale_price_kopeks', note='shown with format_price'),
    ColumnRef('discount_offers', 'bonus_amount_kopeks', note='display-only today, see FINDINGS F-035'),
    ColumnRef('guest_purchases', 'amount_kopeks'),
    ColumnRef('payment_method_configs', 'min_amount_kopeks', note='cabinet top-up scale (Toman x100)'),
    ColumnRef('payment_method_configs', 'max_amount_kopeks', note='cabinet top-up scale (Toman x100)'),
    ColumnRef('payment_method_configs', 'quick_amounts', 'json_values'),
    ColumnRef('poll_responses', 'reward_amount_kopeks'),
    ColumnRef('polls', 'reward_amount_kopeks'),
    ColumnRef('promo_groups', 'auto_assign_total_spent_kopeks', note='compared with catalog total_spent'),
    ColumnRef('promo_offer_templates', 'bonus_amount_kopeks', note='display-only today, see FINDINGS F-035'),
    ColumnRef(
        'referral_contest_events',
        'amount_kopeks',
        note='live writer is catalog; the diagnostics restore writer is Toman (FINDINGS F-057) and '
        'must be corrected with this migration',
    ),
    ColumnRef('referral_contest_virtual_participants', 'total_amount_kopeks'),
    ColumnRef('server_squads', 'price_kopeks'),
    ColumnRef('squads', 'price_kopeks'),
    ColumnRef('subscription_conversions', 'first_payment_amount_kopeks'),
    ColumnRef(
        'subscription_events',
        'amount_kopeks',
        where="event_type IN ('purchase', 'renewal', 'activation')",
        note='mixed scale per event_type — balance_topup/promocode_activation/campaign_registration are Toman',
    ),
    ColumnRef('subscription_servers', 'paid_price_kopeks'),
    ColumnRef('tariffs', 'daily_price_kopeks'),
    ColumnRef('tariffs', 'device_price_kopeks'),
    ColumnRef('tariffs', 'period_prices', 'json_values'),
    ColumnRef('tariffs', 'price_per_day_kopeks'),
    ColumnRef('tariffs', 'traffic_price_per_gb_kopeks'),
    ColumnRef(
        'tariffs',
        'traffic_topup_packages',
        'json_values',
        note='{gb: price} map; missed by 0115 because the name has no money word — rescaled by 0116',
    ),
    ColumnRef(
        'transactions',
        'amount_kopeks',
        where="type IN ('subscription_payment', 'gift_payment')",
        note='mixed scale per transaction type — the other types are Toman 1:1',
    ),
    ColumnRef('users', 'auto_promo_group_threshold_kopeks'),
    ColumnRef('wheel_prizes', 'prize_value_kopeks'),
    ColumnRef('wheel_prizes', 'promo_balance_bonus_kopeks', note='see FINDINGS F-010'),
    ColumnRef('wheel_spins', 'payment_value_kopeks'),
    ColumnRef('wheel_spins', 'prize_value_kopeks'),
)


#: Columns added to :data:`CATALOG_SCALE_COLUMNS` after revision ``0115`` had already shipped.
#: ``0115`` skips them and its own follow-up revision divides them instead, so replaying the
#: chain on a pre-Phase-C dump converts every column exactly once, in either order.
COLUMNS_RESCALED_AFTER_0115: frozenset[tuple[str, str]] = frozenset(
    {
        ('tariffs', 'traffic_topup_packages'),  # 0116
    }
)


#: Already Toman 1:1 — revision ``0113`` must not touch these.
TOMAN_SCALE_COLUMNS: tuple[ColumnRef, ...] = (
    ColumnRef('advertising_campaign_registrations', 'balance_bonus_kopeks'),
    ColumnRef('advertising_campaigns', 'balance_bonus_kopeks', note='credited 1:1 by campaign_service'),
    ColumnRef('c2c_receipts', 'amount_kopeks'),
    ColumnRef('c2c_receipts', 'approved_amount_kopeks'),
    ColumnRef(
        'promocodes',
        'balance_bonus_kopeks',
        note='raw Toman post-Phase-B; for PromoCodeType.DISCOUNT it is a percent, not money',
    ),
    ColumnRef('referral_earnings', 'amount_kopeks'),
    ColumnRef('referral_reward_levels', 'referee_fixed_kopeks'),
    ColumnRef('referral_reward_levels', 'referrer_fixed_kopeks'),
    ColumnRef('users', 'balance_kopeks'),
    ColumnRef('withdrawal_requests', 'amount_kopeks'),
)


#: Not Toman at all: a payment provider's own currency (ruble kopeks, USDT, …) or a non-money unit.
#: Deferred Russian gateways keep their tables untouched by Phase C, by the workspace rule that we
#: never edit their flows. Revision ``0113`` must not touch these either.
PROVIDER_CURRENCY_COLUMNS: tuple[ColumnRef, ...] = (
    ColumnRef('antilopay_payments', 'amount_kopeks'),
    ColumnRef('apple_transactions', 'amount_kopeks'),
    ColumnRef('apple_transactions', 'price_micros'),
    ColumnRef('aurapay_payments', 'amount_kopeks'),
    ColumnRef('cispay_payments', 'amount_kopeks'),
    ColumnRef('cispay_payments', 'charged_amount_kopeks'),
    ColumnRef('cloudpayments_payments', 'amount_kopeks'),
    ColumnRef('cryptobot_payments', 'amount', note='crypto asset units as a string'),
    ColumnRef('donut_payments', 'amount_kopeks'),
    ColumnRef('etoplatezhi_payments', 'amount_kopeks'),
    ColumnRef('freekassa_payments', 'amount_kopeks'),
    ColumnRef('heleket_payments', 'amount'),
    ColumnRef('heleket_payments', 'payer_amount'),
    ColumnRef('jupiter_payments', 'amount_kopeks'),
    ColumnRef('kassa_ai_payments', 'amount_kopeks'),
    ColumnRef('lava_payments', 'amount_kopeks'),
    ColumnRef('lava_subscriptions', 'amount_kopeks'),
    ColumnRef('mulenpay_payments', 'amount_kopeks'),
    ColumnRef('overpay_payments', 'amount_kopeks'),
    ColumnRef('pal24_payments', 'amount_kopeks'),
    ColumnRef('pal24_payments', 'balance_amount'),
    ColumnRef('paypear_payments', 'amount_kopeks'),
    ColumnRef('platega_payments', 'amount_kopeks'),
    ColumnRef('platega_subscriptions', 'amount_kopeks'),
    ColumnRef('riopay_payments', 'amount_kopeks'),
    ColumnRef('rollypay_payments', 'amount_kopeks'),
    ColumnRef('severpay_payments', 'amount_kopeks'),
    ColumnRef('wata_payments', 'amount_kopeks'),
    ColumnRef('wheel_spins', 'payment_amount', note='Telegram Stars count, not currency'),
    ColumnRef('yookassa_payments', 'amount_kopeks'),
)


ALL_CLASSIFIED_COLUMNS: dict[tuple[str, str], str] = {
    **{(ref.table, ref.column): 'catalog' for ref in CATALOG_SCALE_COLUMNS},
    **{(ref.table, ref.column): 'toman' for ref in TOMAN_SCALE_COLUMNS},
    **{(ref.table, ref.column): 'provider' for ref in PROVIDER_CURRENCY_COLUMNS},
}


def scale_of(table: str, column: str) -> str | None:
    """``'catalog'`` | ``'toman'`` | ``'provider'``, or ``None`` when the column is unclassified."""
    return ALL_CLASSIFIED_COLUMNS.get((table, column))


def looks_like_money_column(name: str) -> bool:
    """True when a column name must be classified in this module."""
    return bool(MONEY_COLUMN_NAME_PATTERN.search(name))
