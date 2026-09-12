"""0113 creates the grace_access_sessions table deferred by the grafted 0111 lineage.

0111 added the grace *marker columns* on ``subscriptions`` but deliberately left the table out
(``test_0111_remnawave_id.FORBIDDEN_TABLES``), so upstream's grace-access runtime was compiled in
but could never run. This revision ports the table part of upstream ``0097_add_grace_access``,
adapted to our model: ``remnawave_uuid`` nullable and the numeric ``remnawave_id`` present, as
upstream's ``0104_remnawave_numeric_id`` left them.

The delete-guard trigger is NOT this revision's business: ``_ensure_runtime_schema_guards``
(app/database/migrations.py) owns it and installs it on the next start once the table exists.
One owner, no duplicate DDL.
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
REVISION_FILE = VERSIONS / '0113_create_grace_access_sessions.py'

TABLE = 'grace_access_sessions'
TRIGGER = 'trg_guard_open_grace_subscription_delete'

# Every column of GraceAccessSessionModel (app/database/models.py) — the source of truth.
MODEL_COLUMNS = {
    'id',
    'subscription_id',
    'remnawave_id',
    'remnawave_uuid',
    'reason',
    'incident_key',
    'state',
    'snapshot_version',
    'version',
    'billing_before',
    'panel_before',
    'overlay',
    'started_at',
    'grace_until',
    'updated_at',
    'completion_reason',
    'completed_at',
    'last_error',
}

CHECK_CONSTRAINTS = (
    'ck_grace_access_sessions_reason',
    'ck_grace_access_sessions_state',
    'ck_grace_access_sessions_completion',
    'ck_grace_access_sessions_dates',
    'ck_grace_access_sessions_snapshot_version',
    'ck_grace_access_sessions_version',
)

INDEXES = (
    'uq_grace_access_sessions_one_open',
    'ix_grace_access_sessions_state_until',
    'ix_grace_access_sessions_remnawave_id',
)


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))


def _load_revision():
    spec = importlib.util.spec_from_file_location('rev_0113', REVISION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _subscriptions_table(conn) -> None:
    """Minimal 0112-shape ``subscriptions`` so the FK target exists."""
    conn.execute(text('CREATE TABLE subscriptions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL)'))


def _run(direction: str, conn) -> None:
    rev = _load_revision()
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        getattr(rev, direction)()


def test_0113_is_on_the_single_linear_chain() -> None:
    script = _script_directory()
    heads = script.get_heads()
    assert len(heads) == 1, heads
    assert '0113' in [rev.revision for rev in script.walk_revisions(base='base', head=heads[0])]


def test_0113_revises_0112() -> None:
    rev = _load_revision()
    assert rev.revision == '0113'
    assert rev.down_revision == '0112'


def test_0113_upgrade_creates_the_table_with_every_model_column() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _subscriptions_table(conn)
        assert TABLE not in inspect(conn).get_table_names()

        _run('upgrade', conn)

        inspector = inspect(conn)
        assert TABLE in inspector.get_table_names()
        assert {c['name'] for c in inspector.get_columns(TABLE)} == MODEL_COLUMNS
        assert {idx['name'] for idx in inspector.get_indexes(TABLE)} >= set(INDEXES)


def test_0113_upgrade_creates_the_check_constraints_and_partial_unique_index() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _subscriptions_table(conn)
        _run('upgrade', conn)

        table_sql = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :name"),
            {'name': TABLE},
        ).scalar_one()
        for name in CHECK_CONSTRAINTS:
            assert name in table_sql, name
        assert 'uq_grace_access_sessions_incident' in table_sql

        one_open_sql = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'index' AND name = :name"),
            {'name': 'uq_grace_access_sessions_one_open'},
        ).scalar_one()
        # Partial: at most one *open* session per subscription, closed history unconstrained.
        assert 'WHERE' in one_open_sql.upper()
        assert "'restoring'" in one_open_sql


def test_0113_enforces_one_open_session_per_subscription() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _subscriptions_table(conn)
        conn.execute(text('INSERT INTO subscriptions (id, user_id) VALUES (1, 1)'))
        _run('upgrade', conn)

        def insert(session_id: str, state: str, incident: str) -> None:
            conn.execute(
                text(
                    """
                    INSERT INTO grace_access_sessions (
                        id, subscription_id, reason, incident_key, state,
                        snapshot_version, version, billing_before, panel_before, overlay,
                        started_at, grace_until, updated_at
                    ) VALUES (
                        :id, 1, 'expired', :incident, :state,
                        2, 1, '{}', '{}', '{}',
                        '2026-01-01 00:00:00+00', '2026-01-02 00:00:00+00', '2026-01-01 00:00:00+00'
                    )
                    """
                ),
                {'id': session_id, 'state': state, 'incident': incident},
            )

        insert('s1', 'active', 'i1')
        try:
            insert('s2', 'pending', 'i2')
        except Exception:
            pass
        else:
            raise AssertionError('a second open grace session was accepted')

        # A completed session does not occupy the open slot.
        conn.execute(
            text(
                """
                UPDATE grace_access_sessions
                SET state = 'completed', completion_reason = 'paid', completed_at = '2026-01-02 00:00:00+00'
                WHERE id = 's1'
                """
            )
        )
        insert('s3', 'pending', 'i3')


def test_0113_upgrade_is_a_no_op_when_the_table_already_exists() -> None:
    """Fresh installs are built by ``create_all``, so they already have the table."""
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _subscriptions_table(conn)
        _run('upgrade', conn)
        before = (
            conn.execute(
                text('SELECT name FROM sqlite_master WHERE tbl_name = :name ORDER BY name'),
                {'name': TABLE},
            )
            .scalars()
            .all()
        )

        _run('upgrade', conn)

        after = (
            conn.execute(
                text('SELECT name FROM sqlite_master WHERE tbl_name = :name ORDER BY name'),
                {'name': TABLE},
            )
            .scalars()
            .all()
        )
        assert before == after


def test_0113_downgrade_removes_the_table() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _subscriptions_table(conn)
        _run('upgrade', conn)
        _run('downgrade', conn)

        assert TABLE not in inspect(conn).get_table_names()
        leftover = (
            conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'index' "
                    "AND name IN ('uq_grace_access_sessions_one_open', 'ix_grace_access_sessions_state_until')"
                )
            )
            .scalars()
            .all()
        )
        assert not leftover


def test_0113_does_not_install_the_delete_guard() -> None:
    """``_ensure_runtime_schema_guards`` is the single owner of the trigger."""
    assert 'CREATE TRIGGER' not in REVISION_FILE.read_text(encoding='utf-8').upper()

    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        _subscriptions_table(conn)
        _run('upgrade', conn)
        installed = (
            conn.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger' AND name = :name"),
                {'name': TRIGGER},
            )
            .scalars()
            .all()
        )
        assert not installed


def test_0113_does_not_touch_subscriptions() -> None:
    """The grace marker columns and their indexes already came with 0111."""
    source = REVISION_FILE.read_text(encoding='utf-8')
    assert "add_column('subscriptions'" not in source
    assert "create_index('ix_subscriptions_grace" not in source
