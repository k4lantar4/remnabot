"""Startup delete-guard must respect a deferred ``grace_access_sessions`` table.

0111 deliberately does not create ``grace_access_sessions`` on the remnabot lineage
(``test_0111_remnawave_id.FORBIDDEN_TABLES``), but ``_ensure_runtime_schema_guards`` installed a
BEFORE DELETE trigger on ``subscriptions`` that reads that table. Without the table every
subscription delete then fails, so the guard may only exist while the table does.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

import app.database.database as database_module
from app.database.migrations import _ensure_runtime_schema_guards


TRIGGER = 'trg_guard_open_grace_subscription_delete'


@pytest.fixture(autouse=True)
def real_aiosqlite(monkeypatch):
    # tests/conftest.py stubs ``aiosqlite`` with an empty module; these tests need the real driver.
    monkeypatch.delitem(sys.modules, 'aiosqlite', raising=False)
    monkeypatch.setitem(sys.modules, 'aiosqlite', importlib.import_module('aiosqlite'))


async def _make_engine(tmp_path: Path, *, with_grace_table: bool) -> AsyncEngine:
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "guards.sqlite3"}')
    async with engine.begin() as conn:
        await conn.execute(text('CREATE TABLE subscriptions (id INTEGER PRIMARY KEY)'))
        if with_grace_table:
            await conn.execute(
                text(
                    'CREATE TABLE grace_access_sessions ('
                    'id TEXT PRIMARY KEY, subscription_id INTEGER NOT NULL, state TEXT NOT NULL)'
                )
            )
        await conn.execute(text('INSERT INTO subscriptions (id) VALUES (1)'))
    return engine


async def _trigger_exists(engine: AsyncEngine) -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = :name"), {'name': TRIGGER}
        )
        return result.scalar() is not None


async def _delete_subscription(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text('DELETE FROM subscriptions WHERE id = 1'))


@pytest.mark.asyncio
async def test_guard_is_not_installed_while_grace_table_is_deferred(tmp_path, monkeypatch) -> None:
    engine = await _make_engine(tmp_path, with_grace_table=False)
    monkeypatch.setattr(database_module, 'engine', engine)
    try:
        await _ensure_runtime_schema_guards()

        assert not await _trigger_exists(engine)
        await _delete_subscription(engine)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_orphaned_guard_is_dropped_when_grace_table_is_missing(tmp_path, monkeypatch) -> None:
    engine = await _make_engine(tmp_path, with_grace_table=True)
    monkeypatch.setattr(database_module, 'engine', engine)
    try:
        await _ensure_runtime_schema_guards()
        assert await _trigger_exists(engine)
        async with engine.begin() as conn:
            await conn.execute(text('DROP TABLE grace_access_sessions'))

        await _ensure_runtime_schema_guards()

        assert not await _trigger_exists(engine)
        await _delete_subscription(engine)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_guard_still_blocks_open_session_delete_when_table_exists(tmp_path, monkeypatch) -> None:
    engine = await _make_engine(tmp_path, with_grace_table=True)
    monkeypatch.setattr(database_module, 'engine', engine)
    try:
        await _ensure_runtime_schema_guards()
        assert await _trigger_exists(engine)
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO grace_access_sessions (id, subscription_id, state) VALUES ('s1', 1, 'active')")
            )

        with pytest.raises(DBAPIError, match='open grace-access session'):
            await _delete_subscription(engine)
    finally:
        await engine.dispose()
