"""0117 creates the upstream tables our Alembic lineage deferred at 0111.

At 0095 our lineage forked from upstream's under the same revision numbers, so upstream's
``0095_add_coupons``, ``0099_add_platega_subscriptions`` and friends were archived, not grafted —
while their models kept arriving with every upstream sync. The result: code compiled against
tables that exist only on databases built by ``Base.metadata.create_all``. Two admin screens 500
on a migrated database (``/admin/payments`` reads ``cispay_payments``, the user Activity tab reads
``coupons``), and the gift/guest flow selects ``guest_purchases.idempotency_key``, a column
upstream added in its own archived ``0107``.

This revision creates those tables and adds the two missing columns. Creating a deferred gateway's
table is not enabling it: CisPay, Platega and Lava stay off by their ``*_ENABLED`` flags, and the
schema exists only so a shared query stops raising ``UndefinedTable``.

``referral_reward_levels`` stays deferred on purpose (product decision M4-T1,
``test_0111_remnawave_id.FORBIDDEN_TABLES``) and must NOT appear here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.database.models import Base


ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / 'migrations' / 'alembic' / 'versions'
REVISION_FILE = VERSIONS / '0117_create_deferred_upstream_tables.py'

TABLES = (
    'cispay_payments',
    'platega_subscriptions',
    'lava_subscriptions',
    'recurrent_payments',
    'coupon_batches',
    'coupons',
    'legal_consents',
)

GUEST_PURCHASE_COLUMNS = ('campaign_slug', 'idempotency_key')

#: Deferred by product decision, not by accident — this revision must leave it alone.
STILL_DEFERRED = 'referral_reward_levels'


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))


def _load_revision():
    spec = importlib.util.spec_from_file_location('rev_0117', REVISION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _guest_purchases_table(conn) -> None:
    """Minimal pre-0117 ``guest_purchases`` — the two columns are what this revision adds."""
    conn.execute(text('CREATE TABLE guest_purchases (id INTEGER PRIMARY KEY, token VARCHAR(64))'))


def _run(direction: str, conn) -> None:
    rev = _load_revision()
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        getattr(rev, direction)()


def test_0117_is_on_the_single_linear_chain() -> None:
    script = _script_directory()
    heads = script.get_heads()
    assert len(heads) == 1, heads
    assert '0117' in [rev.revision for rev in script.walk_revisions(base='base', head=heads[0])]


def test_0117_revises_0116() -> None:
    rev = _load_revision()
    assert rev.revision == '0117'
    assert rev.down_revision == '0116'


def test_0117_creates_every_deferred_table_with_its_model_columns() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn)
        _run('upgrade', conn)

        inspector = inspect(conn)
        created = set(inspector.get_table_names())
        for table in TABLES:
            assert table in created, table
            # The model is the source of truth: a migrated database must end up with exactly
            # what ``create_all`` gives a fresh install, or the next 500 is just a rarer column.
            assert {column['name'] for column in inspector.get_columns(table)} == set(
                Base.metadata.tables[table].columns.keys()
            ), table


def test_0117_adds_the_missing_guest_purchase_columns() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn)
        _run('upgrade', conn)

        inspector = inspect(conn)
        columns = {column['name'] for column in inspector.get_columns('guest_purchases')}
        for column in GUEST_PURCHASE_COLUMNS:
            assert column in columns, column
        # Upstream's uniqueness on the idempotency key is what makes a retried gift purchase
        # land on the existing row instead of charging twice.
        assert 'ux_guest_purchases_idempotency_key' in {
            index['name'] for index in inspector.get_indexes('guest_purchases')
        }


def test_0117_creates_the_partial_alive_indexes_of_the_recurring_gateways() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn)
        _run('upgrade', conn)

        for table in ('platega_subscriptions', 'lava_subscriptions'):
            index_sql = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type = 'index' AND name = :name"),
                {'name': f'uq_{table}_alive'},
            ).scalar_one()
            # One *live* binding per subscription; cancelled history stays unconstrained.
            assert 'WHERE' in index_sql.upper(), table
            assert "'PAST_DUE'" in index_sql, table


def test_0117_leaves_the_product_deferred_table_alone() -> None:
    source = REVISION_FILE.read_text(encoding='utf-8')
    assert f"create_table('{STILL_DEFERRED}'" not in source
    assert f'create_table("{STILL_DEFERRED}"' not in source

    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn)
        _run('upgrade', conn)
        assert STILL_DEFERRED not in set(inspect(conn).get_table_names())


def test_0117_upgrade_is_idempotent() -> None:
    """Fresh installs already have every table from ``create_all``; the revision must no-op."""
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn)
        _run('upgrade', conn)
        _run('upgrade', conn)

        inspector = inspect(conn)
        assert set(TABLES) <= set(inspector.get_table_names())
        columns = {column['name'] for column in inspector.get_columns('guest_purchases')}
        assert set(GUEST_PURCHASE_COLUMNS) <= columns


def test_0117_downgrade_removes_what_it_created() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn)
        _run('upgrade', conn)
        _run('downgrade', conn)

        inspector = inspect(conn)
        remaining = set(inspector.get_table_names())
        for table in TABLES:
            assert table not in remaining, table
        columns = {column['name'] for column in inspector.get_columns('guest_purchases')}
        for column in GUEST_PURCHASE_COLUMNS:
            assert column not in columns, column
