"""Guard for the Toman Phase C money-column inventory.

Every column in ``app.database.models`` whose name looks like money must be classified in
``app.utils.amount_columns`` as catalog scale (x100, divided by revision 0113), Toman 1:1, or a
payment provider's own currency/unit. A new or newly merged upstream money column therefore fails
CI until somebody decides its scale — which is the job
``price_display._BALANCE_SCALE_TRANSACTION_TYPES`` used to do by hand before Phase C deleted it.
"""

from sqlalchemy import JSON

from app.database.models import Base, TransactionType
from app.utils.amount_columns import (
    ALL_CLASSIFIED_COLUMNS,
    CATALOG_SCALE_COLUMNS,
    CATALOG_SCALE_SUBSCRIPTION_EVENT_TYPES,
    CATALOG_SCALE_TRANSACTION_TYPES,
    PRE_PHASE_C_TOMAN_TRANSACTION_TYPES,
    PROVIDER_CURRENCY_COLUMNS,
    TOMAN_SCALE_COLUMNS,
    ColumnRef,
    looks_like_money_column,
    scale_of,
)


MIXED_SCALE_COLUMNS = {('transactions', 'amount_kopeks'), ('subscription_events', 'amount_kopeks')}


def _model_columns() -> set[tuple[str, str]]:
    return {(table.name, column.name) for table in Base.metadata.tables.values() for column in table.columns}


def _model_money_columns() -> set[tuple[str, str]]:
    return {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if looks_like_money_column(column.name)
    }


def _all_refs() -> list[ColumnRef]:
    return [*CATALOG_SCALE_COLUMNS, *TOMAN_SCALE_COLUMNS, *PROVIDER_CURRENCY_COLUMNS]


def test_every_money_column_in_the_models_is_classified() -> None:
    unclassified = sorted(_model_money_columns() - set(ALL_CLASSIFIED_COLUMNS))
    assert not unclassified, (
        'Unclassified money columns — add each to app/utils/amount_columns.py '
        f'(catalog x100, Toman 1:1, or provider currency): {unclassified}'
    )


def test_no_classified_column_is_missing_from_the_models() -> None:
    """Compared against *every* column, not only the money-named ones.

    A column may be classified because of what it holds rather than what it is called —
    ``landing_pages.payment_methods`` carries per-method limits and no money word in its name. That
    is exactly the blind spot the ``0116`` post-mortem asked to close, so listing such a column must
    not read as stale here.
    """
    stale = sorted(set(ALL_CLASSIFIED_COLUMNS) - _model_columns())
    assert not stale, f'Listed columns that no longer exist in the models (renamed or dropped?): {stale}'


def test_each_column_is_classified_exactly_once() -> None:
    keys = [(ref.table, ref.column) for ref in _all_refs()]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    assert not duplicates, f'Columns listed under more than one scale: {duplicates}'


def test_transaction_types_are_split_between_the_two_scales() -> None:
    every_type = {member.value for member in TransactionType}
    balance_types = set(PRE_PHASE_C_TOMAN_TRANSACTION_TYPES)

    assert CATALOG_SCALE_TRANSACTION_TYPES.isdisjoint(balance_types)
    assert CATALOG_SCALE_TRANSACTION_TYPES | balance_types == every_type, (
        'A TransactionType is on neither scale — classify it before it renders 100x off: '
        f'{sorted(every_type - CATALOG_SCALE_TRANSACTION_TYPES - balance_types)}'
    )


def test_mixed_scale_columns_carry_a_row_filter_matching_their_type_set() -> None:
    by_key = {(ref.table, ref.column): ref for ref in CATALOG_SCALE_COLUMNS}

    for key in MIXED_SCALE_COLUMNS:
        assert by_key[key].where, f'{key} is mixed-scale and needs a row filter'

    transactions_where = by_key[('transactions', 'amount_kopeks')].where or ''
    for tx_type in CATALOG_SCALE_TRANSACTION_TYPES:
        assert tx_type in transactions_where
    for tx_type in PRE_PHASE_C_TOMAN_TRANSACTION_TYPES:
        assert tx_type not in transactions_where

    events_where = by_key[('subscription_events', 'amount_kopeks')].where or ''
    for event_type in CATALOG_SCALE_SUBSCRIPTION_EVENT_TYPES:
        assert event_type in events_where
    assert 'balance_topup' not in events_where


def test_json_kind_matches_the_actual_column_type() -> None:
    tables = Base.metadata.tables
    for ref in _all_refs():
        column = tables[ref.table].columns[ref.column]
        is_json = isinstance(column.type, JSON)
        assert is_json == (ref.kind in {'json_values', 'json_records'}), (
            f'{ref.table}.{ref.column}: kind={ref.kind!r} but the column type is {column.type}'
        )


def test_deferred_gateway_tables_are_never_on_the_catalog_scale() -> None:
    catalog_tables = {ref.table for ref in CATALOG_SCALE_COLUMNS}
    provider_only = {
        table
        for table in catalog_tables
        if table.endswith('_payments') or table in {'lava_subscriptions', 'platega_subscriptions', 'apple_transactions'}
    }
    assert not provider_only, f'Phase C must not rescale a payment provider table: {sorted(provider_only)}'


def test_scale_of_reports_the_bucket() -> None:
    assert scale_of('tariffs', 'device_price_kopeks') == 'catalog'
    assert scale_of('users', 'balance_kopeks') == 'toman'
    assert scale_of('yookassa_payments', 'amount_kopeks') == 'provider'
    assert scale_of('users', 'telegram_id') is None
