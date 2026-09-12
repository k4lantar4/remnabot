"""The bot refuses to serve unless the database declares the Toman amount scale.

Since Phase C (revisions ``0115``/``0116``) the code reads every stored amount as Toman 1:1. The two
mismatched pairs a deploy can produce — a Phase C image on a database that never ran ``0115``
(migration skipped), or a database still on Toman under a rolled-back image being brought back
without ``alembic upgrade`` — would silently charge or credit 100x. Only the ``toman`` row in
``amount_scale_state`` says which scale the rows are on, so startup checks that row and nothing else.

A fresh database is created from the models and stamped at head, so no revision ever writes that
row there; the bootstrap has to declare the scale itself, or a brand-new install could never start.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

import app.database.database as database_module
from app.database.amount_scale_guard import (
    AmountScaleMismatchError,
    assert_toman_amount_scale,
    declare_toman_scale_on_fresh_db,
)
from app.utils.amount_columns import AMOUNT_SCALE_STATE_TABLE, TOMAN_SCALE


@pytest.fixture(autouse=True)
def real_aiosqlite(monkeypatch):
    # tests/conftest.py stubs ``aiosqlite`` with an empty module; these tests need the real driver.
    monkeypatch.delitem(sys.modules, 'aiosqlite', raising=False)
    monkeypatch.setitem(sys.modules, 'aiosqlite', importlib.import_module('aiosqlite'))


@pytest_asyncio.fixture
async def engine(tmp_path: Path, monkeypatch) -> AsyncEngine:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "scale.sqlite3"}')
    monkeypatch.setattr(database_module, 'engine', engine)
    yield engine
    await engine.dispose()


async def _create_state_table(engine: AsyncEngine, *scales: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f'CREATE TABLE {AMOUNT_SCALE_STATE_TABLE} ('
                'id INTEGER PRIMARY KEY, scale VARCHAR(16) NOT NULL, applied_at TIMESTAMP NOT NULL)'
            )
        )
        for scale in scales:
            await conn.execute(
                text(f"INSERT INTO {AMOUNT_SCALE_STATE_TABLE} (scale, applied_at) VALUES (:scale, '2026-09-12')"),
                {'scale': scale},
            )


async def _marker_rows(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as conn:
        result = await conn.execute(text(f'SELECT scale FROM {AMOUNT_SCALE_STATE_TABLE} ORDER BY id'))
        return [row[0] for row in result]


@pytest.mark.asyncio
async def test_passes_when_the_database_declares_toman(engine) -> None:
    await _create_state_table(engine, TOMAN_SCALE)

    await assert_toman_amount_scale()


@pytest.mark.asyncio
async def test_refuses_a_database_that_predates_0114(engine) -> None:
    with pytest.raises(AmountScaleMismatchError, match='0116'):
        await assert_toman_amount_scale()


@pytest.mark.asyncio
async def test_refuses_when_the_tables_exist_but_0115_never_ran(engine) -> None:
    # 0114 alone (or a downgrade to 0114) leaves the table empty: the table existing means nothing.
    await _create_state_table(engine)

    with pytest.raises(AmountScaleMismatchError):
        await assert_toman_amount_scale()


@pytest.mark.asyncio
async def test_refuses_an_unknown_scale_and_reads_only_the_latest_row(engine) -> None:
    await _create_state_table(engine, TOMAN_SCALE, 'catalog_x100')

    with pytest.raises(AmountScaleMismatchError, match='catalog_x100'):
        await assert_toman_amount_scale()


@pytest.mark.asyncio
async def test_fresh_database_bootstrap_declares_toman_once(engine) -> None:
    await declare_toman_scale_on_fresh_db()
    await declare_toman_scale_on_fresh_db()

    assert await _marker_rows(engine) == [TOMAN_SCALE]
    await assert_toman_amount_scale()


@pytest.mark.asyncio
async def test_fresh_bootstrap_never_overrides_an_existing_declaration(engine) -> None:
    await _create_state_table(engine, 'catalog_x100')

    await declare_toman_scale_on_fresh_db()

    assert await _marker_rows(engine) == ['catalog_x100']
