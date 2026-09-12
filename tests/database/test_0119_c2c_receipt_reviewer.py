"""0119 adds the cabinet reviewer columns to ``c2c_receipts`` on the single linear chain."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.database.models import C2cReceipt


ROOT = Path(__file__).resolve().parents[2]
REVISION_FILE = ROOT / 'migrations' / 'alembic' / 'versions' / '0119_c2c_receipt_reviewer.py'


def _script_directory() -> ScriptDirectory:
    config = Config(str(ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(ROOT / 'migrations' / 'alembic'))
    return ScriptDirectory.from_config(config)


def _load_revision():
    spec = importlib.util.spec_from_file_location('rev_0119', REVISION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_0119_is_on_the_single_linear_chain() -> None:
    script = _script_directory()
    heads = script.get_heads()
    assert len(heads) == 1, heads
    assert '0119' in [rev.revision for rev in script.walk_revisions(base='base', head=heads[0])]


def test_0119_revises_0118() -> None:
    rev = _load_revision()
    assert rev.revision == '0119'
    assert rev.down_revision == '0118'


def test_model_carries_the_reviewer_columns() -> None:
    columns = C2cReceipt.__table__.columns
    assert columns['reviewed_by_user_id'].nullable
    assert {fk.column.table.name for fk in columns['reviewed_by_user_id'].foreign_keys} == {'users'}
    assert columns['reviewed_via'].nullable
    assert columns['reviewed_via'].type.length == 16
