"""Свежая установка и обновлённая обязаны прийти к одной схеме ``referral_earnings``.

Колонки наград (``reward_type``, ``level``, ``days_granted``, ``tariff_id``) в нашей
цепочке добавляет ``0112`` — не апстримовские ``0108``/``0109``: те в граф не
вошли (архив ``docs/superpowers/reference/upstream-alembic-0088-0110/``), а таблица
``referral_reward_levels`` отложена (``test_0111_remnawave_id.FORBIDDEN_TABLES``).

Свежая база создаётся ``Base.metadata.create_all`` по модели, обновлённая —
миграцией. Проверяется через SQLite: диалект другой, но состав колонок и их
описание — то, что расходилось, — от него не зависит.
"""

import importlib.util
import pathlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.database.models import Base, ReferralEarning


VERSIONS = pathlib.Path(__file__).resolve().parents[2] / 'migrations/alembic/versions'
MIGRATION = '0112_referral_earnings_reward_columns.py'

# Колонки, которые заводит сама миграция. Прежние в referral_earnings сравнивать
# нельзя: «старая» база в этом тесте описана рукописным DDL, и расхождение в
# них говорило бы о фикстуре, а не о миграции.
_ADDED_EARNING_COLUMNS = ('reward_type', 'level', 'days_granted', 'tariff_id')


def _load_migration():
    spec = importlib.util.spec_from_file_location('migration_0112', VERSIONS / MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine, step: str) -> None:
    module = _load_migration()
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            getattr(module, step)()


def _fresh_install(path: pathlib.Path):
    """База, созданная по модели, — как на новой установке."""
    engine = sa.create_engine(f'sqlite:///{path}')
    Base.metadata.create_all(
        engine,
        tables=[Base.metadata.tables['tariffs'], ReferralEarning.__table__],
        checkfirst=True,
    )
    return engine


def _upgraded_install(path: pathlib.Path):
    """База в состоянии «до 0112», прогнанная миграцией."""
    engine = sa.create_engine(f'sqlite:///{path}')
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE tariffs (id INTEGER PRIMARY KEY, name VARCHAR(100))'))
        conn.execute(
            sa.text(
                'CREATE TABLE referral_earnings ('
                ' id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, referral_id INTEGER NOT NULL,'
                ' amount_kopeks INTEGER NOT NULL, reason VARCHAR(100) NOT NULL,'
                ' referral_transaction_id INTEGER, campaign_id INTEGER, created_at TIMESTAMP)'
            )
        )
    _run(engine, 'upgrade')
    return engine


@pytest.fixture
def both(tmp_path):
    fresh = _fresh_install(tmp_path / 'fresh.db')
    upgraded = _upgraded_install(tmp_path / 'upgraded.db')
    return sa.inspect(fresh), sa.inspect(upgraded)


def _shape(inspector, table: str) -> dict[str, tuple[str, bool, str | None]]:
    """Колонка -> (тип, nullable, серверный дефолт)."""
    shape = {}
    for column in inspector.get_columns(table):
        default = column.get('default')
        shape[column['name']] = (
            str(column['type']).upper(),
            bool(column['nullable']),
            None if default is None else str(default).strip('\'" '),
        )
    return shape


def test_new_earning_columns_match(both):
    fresh, upgraded = both
    new = set(_ADDED_EARNING_COLUMNS)
    assert new <= {c['name'] for c in fresh.get_columns('referral_earnings')}
    assert new <= {c['name'] for c in upgraded.get_columns('referral_earnings')}


def test_earning_column_shapes_match(both):
    """Имена совпадать могут, а типы, NOT NULL и дефолты — нет: DDL в миграции ручной."""
    fresh, upgraded = both
    fresh_shape, upgraded_shape = _shape(fresh, 'referral_earnings'), _shape(upgraded, 'referral_earnings')
    mismatched = [
        f'{name}: свежая={fresh_shape.get(name)} обновлённая={upgraded_shape.get(name)}'
        for name in sorted(_ADDED_EARNING_COLUMNS)
        if fresh_shape.get(name) != upgraded_shape.get(name)
    ]
    assert mismatched == [], 'referral_earnings: колонки описаны по-разному\n' + '\n'.join(mismatched)


def test_no_duplicate_tariff_foreign_key(both):
    """Миграция не должна вешать второй FK на tariff_id поверх созданного по модели."""
    fresh, upgraded = both
    for inspector, label in ((fresh, 'свежая'), (upgraded, 'обновлённая')):
        tariff_fks = [
            fk
            for fk in inspector.get_foreign_keys('referral_earnings')
            if 'tariff_id' in (fk.get('constrained_columns') or [])
        ]
        assert len(tariff_fks) <= 1, f'{label}: внешних ключей на tariff_id {len(tariff_fks)}'


def test_downgrade_removes_everything_it_added(tmp_path):
    """Откат возвращает исходный вид, и повторный upgrade после него проходит."""
    engine = _upgraded_install(tmp_path / 'roundtrip.db')

    _run(engine, 'downgrade')
    remaining = {c['name'] for c in sa.inspect(engine).get_columns('referral_earnings')}
    assert not (remaining & set(_ADDED_EARNING_COLUMNS)), remaining

    _run(engine, 'upgrade')
    restored = {c['name'] for c in sa.inspect(engine).get_columns('referral_earnings')}
    assert set(_ADDED_EARNING_COLUMNS) <= restored


def test_upgrade_is_idempotent(tmp_path):
    """Повторный прогон на уже обновлённой базе не должен падать."""
    engine = _upgraded_install(tmp_path / 'twice.db')
    _run(engine, 'upgrade')
    columns = {c['name'] for c in sa.inspect(engine).get_columns('referral_earnings')}
    assert set(_ADDED_EARNING_COLUMNS) <= columns


def test_reward_levels_table_is_not_created(tmp_path):
    """0112 сознательно не создаёт отложенную таблицу referral_reward_levels."""
    engine = _upgraded_install(tmp_path / 'deferred.db')
    assert 'referral_reward_levels' not in sa.inspect(engine).get_table_names()
