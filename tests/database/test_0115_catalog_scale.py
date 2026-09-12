"""0115 moves catalog amounts onto the Toman 1:1 scale, reversibly.

The round-trip matters more than the division itself: if ``downgrade()`` cannot restore the exact
pre-migration numbers, a rollback of Phase C would silently rewrite real money.

0114 (the bookkeeping tables) runs first here, as it will in the chain; that it changes nothing on
its own is asserted in ``test_0114_scale_tables.py``.

0115 was staged outside ``migrations/alembic/versions/`` until plan Task 3, so that no restart
could apply it before the code that reads Toman existed. Task 3 shipped that code, so it now sits in
the chain as the head — and the first restart after that merge is what rescales the database.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.config import settings
from app.utils.amount_columns import CATALOG_SCALE_COLUMNS, COLUMNS_RESCALED_AFTER_0115


ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / 'migrations' / 'alembic' / 'versions'
REVISION_FILE = VERSIONS / '0115_toman_phase_c_catalog_scale.py'
TABLES_REVISION_FILE = VERSIONS / '0114_toman_phase_c_scale_tables.py'


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_revision():
    return _load('rev_0115', REVISION_FILE)


def _load_tables_revision():
    return _load('rev_0114', TABLES_REVISION_FILE)


# ── schema and seed ───────────────────────────────────────────────────────────

_metadata = sa.MetaData()

_tariffs = sa.Table(
    'tariffs',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('period_prices', sa.JSON),
    sa.Column('traffic_topup_packages', sa.JSON),
    sa.Column('device_price_kopeks', sa.Integer),
    sa.Column('traffic_price_per_gb_kopeks', sa.Integer),
    sa.Column('daily_price_kopeks', sa.Integer),
    sa.Column('price_per_day_kopeks', sa.Integer),
)
_transactions = sa.Table(
    'transactions',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('type', sa.String(40)),
    sa.Column('amount_kopeks', sa.Integer),
    sa.Column('created_at', sa.DateTime(timezone=True)),
)
_subscription_events = sa.Table(
    'subscription_events',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('event_type', sa.String(40)),
    sa.Column('amount_kopeks', sa.Integer),
)
_users = sa.Table(
    'users',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('balance_kopeks', sa.Integer),
    sa.Column('auto_promo_group_threshold_kopeks', sa.BigInteger),
    sa.Column('created_at', sa.DateTime(timezone=True)),
)
_c2c_receipts = sa.Table(
    'c2c_receipts',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('amount_kopeks', sa.Integer),
)
_yookassa_payments = sa.Table(
    'yookassa_payments',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('amount_kopeks', sa.Integer),
)
_payment_method_configs = sa.Table(
    'payment_method_configs',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('min_amount_kopeks', sa.Integer),
    sa.Column('max_amount_kopeks', sa.Integer),
    sa.Column('quick_amounts', sa.JSON),
)

AFTER_CUTOFF = datetime(2026, 8, 1, tzinfo=UTC)
BEFORE_CUTOFF = datetime(2026, 5, 1, tzinfo=UTC)

# Catalog x100 values of realistic Toman amounts: 50,000 / 1,000,000 …
SEED = {
    'tariffs': [
        {
            'id': 1,
            'period_prices': {'30': 5_000_000, '90': 12_000_000},
            'traffic_topup_packages': {'10': 3_000_000},
            'device_price_kopeks': 100_000,
            'traffic_price_per_gb_kopeks': 700_000,
            'daily_price_kopeks': 1_000_000,
            'price_per_day_kopeks': 0,
        }
    ],
    'transactions': [
        {'id': 1, 'type': 'subscription_payment', 'amount_kopeks': -20_000_000, 'created_at': AFTER_CUTOFF},
        {'id': 2, 'type': 'gift_payment', 'amount_kopeks': -100_000_000, 'created_at': AFTER_CUTOFF},
        {'id': 3, 'type': 'deposit', 'amount_kopeks': 50_000, 'created_at': AFTER_CUTOFF},
        {'id': 4, 'type': 'refund', 'amount_kopeks': 1_000_000, 'created_at': AFTER_CUTOFF},
        # the device-pricing rounding artifact that exists in the dev DB (transactions.id=320)
        {'id': 5, 'type': 'subscription_payment', 'amount_kopeks': -13, 'created_at': AFTER_CUTOFF},
    ],
    'subscription_events': [
        {'id': 1, 'event_type': 'purchase', 'amount_kopeks': 20_000_000},
        {'id': 2, 'event_type': 'renewal', 'amount_kopeks': 5_000_000},
        {'id': 3, 'event_type': 'activation', 'amount_kopeks': 0},
        {'id': 4, 'event_type': 'balance_topup', 'amount_kopeks': 50_000},
    ],
    'users': [
        {
            'id': 1,
            'balance_kopeks': 250_000,
            'auto_promo_group_threshold_kopeks': 100_000_000,
            'created_at': AFTER_CUTOFF,
        }
    ],
    'c2c_receipts': [{'id': 1, 'amount_kopeks': 1_000_000}],
    'yookassa_payments': [{'id': 1, 'amount_kopeks': 99_900}],
    'payment_method_configs': [
        {
            'id': 1,
            'min_amount_kopeks': 10_000_000,
            'max_amount_kopeks': 1_000_000_000,
            'quick_amounts': [10_000_000, 50_000_000],
        }
    ],
}

TABLES = {
    'tariffs': _tariffs,
    'transactions': _transactions,
    'subscription_events': _subscription_events,
    'users': _users,
    'c2c_receipts': _c2c_receipts,
    'yookassa_payments': _yookassa_payments,
    'payment_method_configs': _payment_method_configs,
}


def _seeded_connection(*, extra_transactions: list[dict] | None = None):
    engine = create_engine('sqlite:///:memory:')
    conn = engine.connect()
    _metadata.create_all(conn)
    for name, table in TABLES.items():
        rows = list(SEED[name])
        if name == 'transactions' and extra_transactions:
            rows += extra_transactions
        conn.execute(table.insert(), rows)
    conn.commit()
    return conn


def _run(conn, direction: str) -> None:
    """Apply the Phase C pair in chain order: 0114 then 0115 up, the reverse down."""
    order = [_load_tables_revision(), _load_revision()]
    if direction == 'downgrade':
        order.reverse()
    for rev in order:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            getattr(rev, direction)()
        conn.commit()


def _snapshot(conn) -> dict[str, list[tuple]]:
    snapshot: dict[str, list[tuple]] = {}
    for name, table in TABLES.items():
        columns = ', '.join(column.name for column in table.columns)
        snapshot[name] = [tuple(row) for row in conn.execute(text(f'SELECT {columns} FROM {name} ORDER BY id'))]
    return snapshot


def _value(conn, table: str, column: str, row_id: int):
    return conn.execute(text(f'SELECT {column} FROM {table} WHERE id = :i').bindparams(i=row_id)).scalar()


# ── chain ─────────────────────────────────────────────────────────────────────


def test_the_data_revision_is_reachable_in_the_chain() -> None:
    """Task 3 shipped the code that reads Toman, so the rescale is reachable from the head.

    0115 was the head when it merged; 0116 (the one catalog column it could not see) now follows it.
    """
    assert REVISION_FILE.exists()
    assert not (ROOT / 'migrations' / 'phase_c').exists(), 'the staging directory should be gone'

    script = _script_directory()
    chain = [rev.revision for rev in script.walk_revisions(base='base', head=script.get_current_head())]
    assert '0115' in chain
    assert len(script.get_heads()) == 1, 'the chain must stay linear'


def test_0115_leaves_later_classified_columns_to_their_own_revision() -> None:
    """A column classified as catalog after 0115 shipped is divided by its own revision, not here.

    ``tariffs.traffic_topup_packages`` is the case: 0116 owns it, so replaying the chain on an old
    dump must not divide it twice. See ``test_0116_topup_packages_scale.py``.
    """
    assert ('tariffs', 'traffic_topup_packages') in COLUMNS_RESCALED_AFTER_0115
    for table, column in COLUMNS_RESCALED_AFTER_0115:
        assert (table, column) in {(ref.table, ref.column) for ref in CATALOG_SCALE_COLUMNS}

    conn = _seeded_connection()
    _run(conn, 'upgrade')

    assert _load_revision()._scaled_payload(_value(conn, 'tariffs', 'traffic_topup_packages', 1), divide=False) == {
        '10': 300_000_000
    }


def test_0115_revises_0114() -> None:
    rev = _load_revision()
    assert rev.revision == '0115'
    assert rev.down_revision == '0114'


def test_cutoff_constant_matches_the_settings_value() -> None:
    rev = _load_revision()
    assert settings.balance_toman_cutoff == rev.PRE_TOMAN_CUTOFF_UTC


# ── upgrade ───────────────────────────────────────────────────────────────────


def test_upgrade_divides_catalog_columns_only() -> None:
    conn = _seeded_connection()
    _run(conn, 'upgrade')

    # catalog: tariff prices, including the JSON map
    assert _value(conn, 'tariffs', 'device_price_kopeks', 1) == 1_000
    assert _value(conn, 'tariffs', 'traffic_price_per_gb_kopeks', 1) == 7_000
    assert _value(conn, 'tariffs', 'daily_price_kopeks', 1) == 10_000
    assert _load_revision()._scaled_payload(_value(conn, 'tariffs', 'period_prices', 1), divide=False) == {
        '30': 5_000_000,
        '90': 12_000_000,
    }

    # catalog: only the two catalog transaction types
    assert _value(conn, 'transactions', 'amount_kopeks', 1) == -200_000
    assert _value(conn, 'transactions', 'amount_kopeks', 2) == -1_000_000
    # balance-scale rows keep their Toman value
    assert _value(conn, 'transactions', 'amount_kopeks', 3) == 50_000
    assert _value(conn, 'transactions', 'amount_kopeks', 4) == 1_000_000

    # subscription_events is mixed per event_type, like transactions
    assert _value(conn, 'subscription_events', 'amount_kopeks', 1) == 200_000
    assert _value(conn, 'subscription_events', 'amount_kopeks', 2) == 50_000
    assert _value(conn, 'subscription_events', 'amount_kopeks', 4) == 50_000

    # Toman and provider columns are untouched
    assert _value(conn, 'users', 'balance_kopeks', 1) == 250_000
    assert _value(conn, 'users', 'auto_promo_group_threshold_kopeks', 1) == 1_000_000
    assert _value(conn, 'c2c_receipts', 'amount_kopeks', 1) == 1_000_000
    assert _value(conn, 'yookassa_payments', 'amount_kopeks', 1) == 99_900

    # top-up limits and quick amounts
    assert _value(conn, 'payment_method_configs', 'min_amount_kopeks', 1) == 100_000
    assert _value(conn, 'payment_method_configs', 'max_amount_kopeks', 1) == 10_000_000
    assert _load_revision()._scaled_payload(
        _value(conn, 'payment_method_configs', 'quick_amounts', 1), divide=False
    ) == [
        10_000_000,
        50_000_000,
    ]
    conn.close()


def test_displayed_amount_is_unchanged_by_the_migration() -> None:
    """What the user reads must be identical before and after the rescale.

    The comparison cannot use ``settings.format_price`` for the "before" side any more: Phase C made
    it an alias of ``format_balance`` in the same change that ships this revision, so it no longer
    models the old behaviour. The old formatter floored ``kopeks // 100`` and rendered that, which is
    spelled out here — if this and the migration ever disagree, a price changes under the user.
    """
    conn = _seeded_connection()
    before = {row_id: _value(conn, 'transactions', 'amount_kopeks', row_id) for row_id in (1, 2)}
    _run(conn, 'upgrade')

    for row_id, before_value in before.items():
        after_value = _value(conn, 'transactions', 'amount_kopeks', row_id)
        old_rendering = settings.format_balance(abs(before_value) // 100)
        assert old_rendering == settings.format_balance(abs(after_value))
    conn.close()


def test_upgrade_is_idempotent() -> None:
    conn = _seeded_connection()
    _run(conn, 'upgrade')
    once = _snapshot(conn)
    _run(conn, 'upgrade')
    assert _snapshot(conn) == once
    conn.close()


def test_upgrade_records_the_toman_marker() -> None:
    conn = _seeded_connection()
    _run(conn, 'upgrade')
    assert conn.execute(text('SELECT scale FROM amount_scale_state')).scalar() == 'toman'
    conn.close()


def test_rows_that_lose_precision_are_logged() -> None:
    conn = _seeded_connection()
    _run(conn, 'upgrade')

    logged = conn.execute(
        text('SELECT table_name, column_name, row_id, before_value FROM amount_scale_rounding_log')
    ).fetchall()
    assert [tuple(row) for row in logged] == [('transactions', 'amount_kopeks', 5, -13)]
    assert _value(conn, 'transactions', 'amount_kopeks', 5) == 0
    conn.close()


# ── downgrade ─────────────────────────────────────────────────────────────────


def test_downgrade_restores_every_value_including_the_lossy_row() -> None:
    conn = _seeded_connection()
    before = _snapshot(conn)

    _run(conn, 'upgrade')
    _run(conn, 'downgrade')

    assert _snapshot(conn) == before
    tables = set(sa.inspect(conn).get_table_names())
    assert 'amount_scale_state' not in tables
    assert 'amount_scale_rounding_log' not in tables
    conn.close()


def test_downgrade_without_the_marker_is_a_no_op() -> None:
    conn = _seeded_connection()
    before = _snapshot(conn)
    _run(conn, 'downgrade')
    assert _snapshot(conn) == before
    conn.close()


# ── guard ─────────────────────────────────────────────────────────────────────


def test_upgrade_refuses_to_run_while_pre_phase_b_rows_exist() -> None:
    conn = _seeded_connection(
        extra_transactions=[
            {'id': 99, 'type': 'deposit', 'amount_kopeks': 100_000, 'created_at': BEFORE_CUTOFF},
        ]
    )
    before = _snapshot(conn)

    with pytest.raises(RuntimeError, match='ruble-to-Toman rate'):
        _run(conn, 'upgrade')

    conn.rollback()
    assert _snapshot(conn) == before
    conn.close()
