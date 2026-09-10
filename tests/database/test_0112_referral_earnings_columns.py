"""0112 adds 4.2 referral_earnings reward columns on the grafted 0111 lineage."""

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
REVISION_FILE = VERSIONS / '0112_referral_earnings_reward_columns.py'


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ROOT / 'alembic.ini')))


def _load_revision():
    spec = importlib.util.spec_from_file_location('rev_0112', REVISION_FILE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_0112_is_the_single_head() -> None:
    heads = _script_directory().get_heads()
    assert heads == ['0112'], heads


def test_0112_revises_0111() -> None:
    rev = _load_revision()
    assert rev.revision == '0112'
    assert rev.down_revision == '0111'


def test_0112_source_does_not_create_deferred_tables() -> None:
    source = REVISION_FILE.read_text(encoding='utf-8')
    assert "create_table('referral_reward_levels'" not in source
    assert 'create_table("referral_reward_levels"' not in source


def test_0112_upgrade_adds_reward_columns() -> None:
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tariffs (id INTEGER PRIMARY KEY)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE referral_earnings (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    referral_id INTEGER NOT NULL,
                    amount_kopeks INTEGER NOT NULL,
                    reason VARCHAR(100) NOT NULL
                )
                """
            )
        )
        rev = _load_revision()
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            rev.upgrade()
            rev.upgrade()
        cols = {c['name'] for c in inspect(conn).get_columns('referral_earnings')}
        assert {'reward_type', 'level', 'days_granted', 'tariff_id'} <= cols
