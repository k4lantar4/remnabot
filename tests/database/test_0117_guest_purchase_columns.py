"""0117 adds the two ``guest_purchases`` columns our forked Alembic lineage never got.

Upstream's ``0106_guest_purchase_campaign`` and ``0107_guest_purchase_idempotency`` were archived
when our chain forked at 0095, but the model (``GuestPurchase`` in app/database/models.py) and the
code that reads ``idempotency_key`` came in with later upstream syncs. Any ORM ``SELECT`` names
every mapped column, so on a migrated database the cabinet dashboard and ``/admin/users`` fail with
``UndefinedColumnError``. This revision ports both columns onto our lineage after 0116.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / 'migrations' / 'alembic' / 'versions'
REVISION_FILE = VERSIONS / '0117_guest_purchase_campaign_and_idempotency.py'

TABLE = 'guest_purchases'
NEW_COLUMNS = ('campaign_slug', 'idempotency_key')
UNIQUE_INDEX = 'ux_guest_purchases_idempotency_key'


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))


def _load_revision():
    spec = importlib.util.spec_from_file_location('rev_0117', REVISION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _guest_purchases_table(conn, *, with_new_columns: bool = False) -> None:
    """Minimal 0116-shape ``guest_purchases`` (fresh installs also carry the new columns)."""
    extra = ', campaign_slug VARCHAR(64), idempotency_key VARCHAR(64)' if with_new_columns else ''
    conn.execute(
        text(
            'CREATE TABLE guest_purchases (id INTEGER PRIMARY KEY, token VARCHAR(64), status VARCHAR(32)' + extra + ')'
        )
    )


def _run(direction: str, conn) -> None:
    rev = _load_revision()
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        getattr(rev, direction)()


def test_0117_is_the_single_head_on_the_linear_chain() -> None:
    script = _script_directory()
    heads = script.get_heads()
    assert heads == ['0117'], heads
    assert '0117' in [rev.revision for rev in script.walk_revisions(base='base', head=heads[0])]


def test_0117_revises_0116() -> None:
    rev = _load_revision()
    assert rev.revision == '0117'
    assert rev.down_revision == '0116'


def test_0117_upgrade_adds_both_columns_and_the_unique_index() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn)
        assert {c['name'] for c in inspect(conn).get_columns(TABLE)}.isdisjoint(NEW_COLUMNS)

        _run('upgrade', conn)

        inspector = inspect(conn)
        assert {c['name'] for c in inspector.get_columns(TABLE)} >= set(NEW_COLUMNS)
        indexes = {idx['name']: idx for idx in inspector.get_indexes(TABLE)}
        assert UNIQUE_INDEX in indexes
        assert indexes[UNIQUE_INDEX]['unique']  # sqlite reports 1, postgres True


def test_0117_unique_index_rejects_a_duplicate_key_but_allows_many_nulls() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn)
        _run('upgrade', conn)

        def insert(row_id: int, key: str | None) -> None:
            conn.execute(
                text('INSERT INTO guest_purchases (id, idempotency_key) VALUES (:id, :key)'),
                {'id': row_id, 'key': key},
            )

        insert(1, 'checkout-1')
        try:
            insert(2, 'checkout-1')
        except Exception:
            pass
        else:
            raise AssertionError('a duplicate idempotency_key was accepted')

        # Purchases made before the column existed keep NULL — the index must not collapse them.
        insert(3, None)
        insert(4, None)


def test_0117_upgrade_is_a_no_op_when_the_columns_already_exist() -> None:
    """Fresh installs are built by ``create_all``, so they already have both columns."""
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn, with_new_columns=True)
        _run('upgrade', conn)
        _run('upgrade', conn)

        inspector = inspect(conn)
        assert {c['name'] for c in inspector.get_columns(TABLE)} >= set(NEW_COLUMNS)
        assert UNIQUE_INDEX in {idx['name'] for idx in inspector.get_indexes(TABLE)}


def test_0117_upgrade_skips_a_database_without_the_table() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _run('upgrade', conn)
        assert TABLE not in inspect(conn).get_table_names()


def test_0117_downgrade_removes_what_it_added() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _guest_purchases_table(conn)
        _run('upgrade', conn)

        _run('downgrade', conn)

        inspector = inspect(conn)
        assert {c['name'] for c in inspector.get_columns(TABLE)}.isdisjoint(NEW_COLUMNS)
        assert UNIQUE_INDEX not in {idx['name'] for idx in inspector.get_indexes(TABLE)}
