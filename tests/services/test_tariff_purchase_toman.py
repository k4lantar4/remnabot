"""The bot's tariff screens, the auto-purchase after a top-up and the remaining balance paths use Toman.

Follow-up to ``test_affordability_toman.py`` (PR #36), with the same numbers and fixtures: the balance
is raw Toman, tariff prices are catalog ``price_kopeks`` (Toman x 100). A 150,000-Toman balance against a
200,000-Toman price (catalog 20,000,000) is refused with a 50,000-Toman shortfall; a 250,000-Toman
balance gets exactly 200,000 debited, while the ledger row keeps the catalog 20,000,000.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.config import Settings, settings
from app.database.models import Subscription, Tariff, Transaction
from tests.fixtures.sqlite_memory import memory_session
from tests.services.test_affordability_toman import (  # noqa: F401 - _isolate is an autouse fixture
    PRICE_KOPEKS,
    PRICE_TOMAN,
    RICH_BALANCE,
    SHORT_BALANCE,
    SHORTFALL_LABEL,
    SHORTFALL_TOMAN,
    TABLES,
    _balance,
    _FakePanelSync,
    _FakeRemnaWave,
    _isolate,
    _loaded_user,
    _payments,
    _seed,
    _spy_debits,
    _switch_cost,
)


AFTER_LABEL = settings.format_balance(RICH_BALANCE - PRICE_TOMAN)  # «50,000 تومان» left after paying


def _callback(data: str) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        from_user=SimpleNamespace(id=1001),
        bot=None,
    )


def _state(data: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        get_data=AsyncMock(return_value=dict(data or {})),
        update_data=AsyncMock(),
        set_state=AsyncMock(),
        clear=AsyncMock(),
    )


def _text(callback) -> str:
    call = callback.message.edit_text.await_args
    return call.args[0] if call.args else call.kwargs.get('text', '')


def _buttons(callback) -> list[str]:
    markup = callback.message.edit_text.await_args.kwargs.get('reply_markup')
    return [button.callback_data or '' for row in markup.inline_keyboard for button in row] if markup else []


def _refused(callback) -> bool:
    """The insufficient-balance screen: its keyboard leads to a top-up."""
    return any(data == 'balance_topup' or data.startswith('topup_amount|') for data in _buttons(callback))


async def _add_daily_tariff(db) -> None:
    db.add(
        Tariff(
            id=3,
            name='daily',
            description='',
            is_active=True,
            is_daily=True,
            daily_price_kopeks=PRICE_KOPEKS,
            period_prices={},
            traffic_limit_gb=100,
            traffic_reset_mode='NO_RESET',
            device_limit=1,
            max_device_limit=10,
            device_price_kopeks=100,
            allowed_squads=['squad-1'],
            display_order=3,
        )
    )
    await db.commit()


def _purchase_price(monkeypatch) -> None:
    """PricingEngine.calculate_tariff_purchase_price pinned to the catalog 20,000,000, no discounts."""
    from app.services.pricing_engine import PricingEngine

    async def fake(self, tariff, period_days, *, device_limit=None, user=None, **kwargs):
        return SimpleNamespace(
            final_total=PRICE_KOPEKS,
            original_total=PRICE_KOPEKS,
            promo_group_discount=0,
            promo_offer_discount=0,
            breakdown={},
        )

    monkeypatch.setattr(PricingEngine, 'calculate_tariff_purchase_price', fake)


@pytest.fixture
def bot_tariffs(monkeypatch):
    """tariff_purchase with the price engine pinned to 20,000,000 and no panel or top-up buttons."""
    import app.services.remnawave_service as remnawave_module
    from app.handlers.subscription import tariff_purchase

    async def resolve(callback, db_user, db, state=None):
        return await db.get(Subscription, 10), 10

    _purchase_price(monkeypatch)
    monkeypatch.setattr(Settings, 'is_auto_purchase_after_topup_enabled', lambda self: False)
    monkeypatch.setattr(settings, 'TARIFF_SWITCH_DOWNGRADE_ENABLED', True, raising=False)
    monkeypatch.setattr(tariff_purchase, '_resolve_switch_subscription', resolve)
    monkeypatch.setattr(tariff_purchase, 'SubscriptionService', lambda: _FakePanelSync())
    monkeypatch.setattr(remnawave_module, 'RemnaWaveService', _FakeRemnaWave)
    return tariff_purchase


async def _run_screen(monkeypatch, handler, data: str, *, balance: int, daily: bool = False, subscription=True):
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=balance, with_subscription=subscription)
        if daily:
            await _add_daily_tariff(db)
        callback = _callback(data)
        await handler(callback, await _loaded_user(db), db, _state())
        assert await _balance(db) == balance  # a preview never charges
    return callback


# ---------------------------------------------------------------- bot tariff screens (pay-from-balance gates)


SCREENS = {
    # name: (handler, callback data, needs the daily tariff, needs an existing subscription)
    'purchase period': ('select_tariff_period', 'tariff_period:2:30', False, False),
    'renewal period': ('select_tariff_extend_period', 'tariff_extend:10:1:30', False, True),
    'switch period': ('select_tariff_switch_period', 'tariff_sw_period:2:30', False, True),
    'switch to daily': ('select_tariff_switch', 'tariff_sw_select:3', True, True),
    'instant switch upgrade': ('preview_instant_switch', 'instant_sw_preview:2', False, True),
    'instant switch to daily': ('preview_instant_switch', 'instant_sw_preview:3', True, True),
}


@pytest.mark.parametrize('screen', sorted(SCREENS))
@pytest.mark.asyncio
async def test_bot_tariff_screen_refuses_with_the_toman_shortfall(monkeypatch, bot_tariffs, screen):
    name, data, daily, subscription = SCREENS[screen]
    _switch_cost(monkeypatch)
    callback = await _run_screen(
        monkeypatch, getattr(bot_tariffs, name), data, balance=SHORT_BALANCE, daily=daily, subscription=subscription
    )

    assert _refused(callback)
    assert SHORTFALL_LABEL in _text(callback)


@pytest.mark.parametrize('screen', sorted(SCREENS))
@pytest.mark.asyncio
async def test_bot_tariff_screen_offers_the_balance_that_covers_the_toman_price(monkeypatch, bot_tariffs, screen):
    name, data, daily, subscription = SCREENS[screen]
    _switch_cost(monkeypatch)
    callback = await _run_screen(
        monkeypatch, getattr(bot_tariffs, name), data, balance=RICH_BALANCE, daily=daily, subscription=subscription
    )

    assert not _refused(callback)
    text = _text(callback)
    assert settings.format_balance(RICH_BALANCE) in text
    if not daily:  # the period screens also show what is left after paying
        assert AFTER_LABEL in text


@pytest.mark.parametrize('balance', [SHORT_BALANCE, RICH_BALANCE])
@pytest.mark.asyncio
async def test_bot_daily_tariff_purchase_screen_uses_the_toman_price(monkeypatch, bot_tariffs, balance):
    from app.services.user_cart_service import user_cart_service

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=balance, with_subscription=False)
        await _add_daily_tariff(db)
        callback = _callback('tariff_select:3')
        await bot_tariffs._proceed_with_selected_tariff(callback, await _loaded_user(db), db, _state(), 3)

    if balance == SHORT_BALANCE:
        assert SHORTFALL_LABEL in _text(callback)
        # the saved cart carries the Toman shortfall and the catalog price
        cart = user_cart_service.save_user_cart.await_args.args[1]
        assert (cart['missing_amount'], cart['total_price']) == (SHORTFALL_TOMAN, PRICE_KOPEKS)
    else:
        assert 'daily_tariff_confirm:3' in _buttons(callback)
        user_cart_service.save_user_cart.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_instant_switch_to_daily_debits_the_toman_first_day(monkeypatch, bot_tariffs):
    _switch_cost(monkeypatch, upgrade_cost=0)  # no prorated upgrade: only the first day is charged
    debits = _spy_debits(monkeypatch, bot_tariffs)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        await _add_daily_tariff(db)
        await bot_tariffs.confirm_instant_switch(
            _callback('instant_sw_confirm:3'), await _loaded_user(db), db, _state()
        )

        assert debits == [PRICE_TOMAN]
        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]
        assert (await db.get(Subscription, 10)).tariff_id == 3


# ---------------------------------------------------------------- bot tariff purchase: refund after rollback


@pytest.mark.parametrize('daily', [False, True])
@pytest.mark.asyncio
async def test_bot_tariff_purchase_refunds_the_toman_price_when_creation_fails(monkeypatch, bot_tariffs, daily):
    """The compensating refund runs after db.rollback(), which expires the user it is given."""
    monkeypatch.setattr(bot_tariffs, 'create_paid_subscription', AsyncMock(side_effect=RuntimeError('db down')))
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE, with_subscription=False)
        await _add_daily_tariff(db)
        user = await _loaded_user(db)
        if daily:
            await bot_tariffs.confirm_daily_tariff_purchase(_callback('daily_tariff_confirm:3'), user, db, _state())
        else:
            await bot_tariffs.confirm_tariff_purchase(_callback('tariff_confirm:2:30'), user, db, _state())

        assert await _balance(db) == RICH_BALANCE
        assert await _payments(db) == [('refund', PRICE_TOMAN)]
        failed = await db.execute(select(Transaction.id).where(Transaction.type == 'failed_refund'))
        assert failed.first() is None
