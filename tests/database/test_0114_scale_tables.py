"""0114 must be safe to apply on its own — it may not change a single amount.

This is the invariant that keeps every commit on ``main`` restart-safe: the bot runs
``alembic upgrade head`` at start, so any revision reachable before the Phase C code is deployed
must leave the stored amounts exactly as they are. The rescale lives in 0115, which ships with that
code.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.utils.amount_columns import AMOUNT_SCALE_ROUNDING_LOG_TABLE, AMOUNT_SCALE_STATE_TABLE


ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / 'migrations' / 'alembic' / 'versions'
REVISION_FILE = VERSIONS / '0114_toman_phase_c_scale_tables.py'


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))


def _load_revision():
    spec = importlib.util.spec_from_file_location('rev_0114', REVISION_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_metadata = sa.MetaData()
_tariffs = sa.Table(
    'tariffs',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('period_prices', sa.JSON),
    sa.Column('device_price_kopeks', sa.Integer),
)
_transactions = sa.Table(
    'transactions',
    _metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('type', sa.String(40)),
    sa.Column('amount_kopeks', sa.Integer),
)


def _seeded_connection():
    engine = create_engine('sqlite:///:memory:')
    conn = engine.connect()
    _metadata.create_all(conn)
    conn.execute(_tariffs.insert(), [{'id': 1, 'period_prices': {'30': 5_000_000}, 'device_price_kopeks': 100_000}])
    conn.execute(
        _transactions.insert(),
        [
            {'id': 1, 'type': 'subscription_payment', 'amount_kopeks': -20_000_000},
            {'id': 2, 'type': 'deposit', 'amount_kopeks': 50_000},
        ],
    )
    conn.commit()
    return conn


def _run(conn, direction: str) -> None:
    rev = _load_revision()
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        getattr(rev, direction)()
    conn.commit()


def _amounts(conn) -> list[tuple]:
    return [
        tuple(row)
        for row in conn.execute(
            text(
                'SELECT id, period_prices, device_price_kopeks FROM tariffs '
                'UNION ALL SELECT id, type, amount_kopeks FROM transactions ORDER BY id'
            )
        )
    ]


def test_0114_revises_0113() -> None:
    rev = _load_revision()
    assert rev.revision == '0114'
    assert rev.down_revision == '0113'


def test_0114_is_on_the_single_linear_chain() -> None:
    script = _script_directory()
    heads = script.get_heads()
    assert len(heads) == 1, heads
    assert '0114' in [rev.revision for rev in script.walk_revisions(base='base', head=heads[0])]


def test_0114_creates_the_bookkeeping_tables() -> None:
    conn = _seeded_connection()
    _run(conn, 'upgrade')

    tables = set(sa.inspect(conn).get_table_names())
    assert AMOUNT_SCALE_STATE_TABLE in tables
    assert AMOUNT_SCALE_ROUNDING_LOG_TABLE in tables
    conn.close()


def test_0114_declares_no_scale_on_its_own() -> None:
    """Creating the table must not be mistaken for 'the database is on the Toman scale'."""
    conn = _seeded_connection()
    _run(conn, 'upgrade')

    assert conn.execute(text(f'SELECT count(*) FROM {AMOUNT_SCALE_STATE_TABLE}')).scalar() == 0
    conn.close()


def test_0114_changes_no_amount() -> None:
    conn = _seeded_connection()
    before = _amounts(conn)

    _run(conn, 'upgrade')

    assert _amounts(conn) == before
    conn.close()


def test_0114_upgrade_is_idempotent() -> None:
    conn = _seeded_connection()
    _run(conn, 'upgrade')
    _run(conn, 'upgrade')

    tables = set(sa.inspect(conn).get_table_names())
    assert AMOUNT_SCALE_STATE_TABLE in tables
    conn.close()


def test_0114_downgrade_drops_the_tables_and_keeps_the_data() -> None:
    conn = _seeded_connection()
    before = _amounts(conn)

    _run(conn, 'upgrade')
    _run(conn, 'downgrade')

    tables = set(sa.inspect(conn).get_table_names())
    assert AMOUNT_SCALE_STATE_TABLE not in tables
    assert AMOUNT_SCALE_ROUNDING_LOG_TABLE not in tables
    assert _amounts(conn) == before
    conn.close()
