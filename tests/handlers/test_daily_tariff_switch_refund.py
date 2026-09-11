"""Daily-tariff switch refunds only a debit that was never delivered (F-032).

The switch is committed before the panel sync, the transaction row and the final
message; all of them sat in the same ``try`` whose ``except`` refunded
unconditionally. A Telegram error on the success message gave the user the
switch *and* the money back; a debit that raised was "refunded" without having
been taken. Harness and numbers from ``tests/services/test_tariff_purchase_toman.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.fixtures.sqlite_memory import memory_session
from tests.services.test_tariff_purchase_toman import (  # noqa: F401 - bot_tariffs, _isolate are fixtures
    PRICE_TOMAN,
    RICH_BALANCE,
    TABLES,
    _add_daily_tariff,
    _balance,
    _callback,
    _failing_commit,
    _isolate,
    _loaded_user,
    _payments,
    _seed,
    _state,
    bot_tariffs,
)


DATA = 'daily_tariff_sw_confirm:3'


async def _seed_daily(db) -> None:
    await _seed(db, balance_toman=RICH_BALANCE, with_subscription=True)
    await _add_daily_tariff(db)


def _refunds(payments) -> list:
    return [row for row in payments if row[0] == 'refund']


@pytest.mark.asyncio
async def test_message_failure_after_the_switch_is_not_refunded(monkeypatch, bot_tariffs):
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_daily(db)
        callback = _callback(DATA)
        callback.message.edit_text = AsyncMock(side_effect=RuntimeError('telegram down'))

        await bot_tariffs.confirm_daily_tariff_switch(callback, await _loaded_user(db), db, _state())

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert _refunds(await _payments(db)) == []


@pytest.mark.asyncio
async def test_failure_before_the_switch_is_committed_refunds_once(monkeypatch, bot_tariffs):
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_daily(db)
        _failing_commit(monkeypatch, db, failing_call=2)  # 1: the debit, 2: the switch

        await bot_tariffs.confirm_daily_tariff_switch(_callback(DATA), await _loaded_user(db), db, _state())

        assert await _balance(db) == RICH_BALANCE
        assert _refunds(await _payments(db)) == [('refund', PRICE_TOMAN)]


@pytest.mark.asyncio
async def test_debit_that_raised_is_not_refunded(monkeypatch, bot_tariffs):
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_daily(db)
        monkeypatch.setattr(bot_tariffs, 'subtract_user_balance', AsyncMock(side_effect=RuntimeError('db down')))

        await bot_tariffs.confirm_daily_tariff_switch(_callback(DATA), await _loaded_user(db), db, _state())

        assert await _balance(db) == RICH_BALANCE
        assert _refunds(await _payments(db)) == []
