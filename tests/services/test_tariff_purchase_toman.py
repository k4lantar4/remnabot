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


# ---------------------------------------------------------------- auto-purchase after a top-up


@pytest.fixture
def auto(monkeypatch):
    """The auto-purchase service with no panel, carts, e-mail, websocket or admin notifications."""
    import app.services.subscription_auto_purchase_service as auto_module
    import app.services.subscription_renewal_service as renewal_module
    from app.cabinet.routes import websocket
    from app.services.pricing_engine import PricingEngine, RenewalPricing, pricing_engine

    async def renewal_price(self, db, subscription, period_days, *, user=None):
        return RenewalPricing(
            base_price=PRICE_KOPEKS,
            servers_price=0,
            traffic_price=0,
            devices_price=0,
            promo_group_discount=0,
            promo_offer_discount=0,
            final_total=PRICE_KOPEKS,
            period_days=period_days,
            is_tariff_mode=True,
            breakdown={},
        )

    pricing_engine.__dict__.pop('calculate_renewal_price', None)
    monkeypatch.setattr(PricingEngine, 'calculate_renewal_price', renewal_price)
    _purchase_price(monkeypatch)
    monkeypatch.setattr(auto_module, 'SubscriptionService', lambda: _FakePanelSync())
    monkeypatch.setattr(auto_module, '_delete_cart_for_subscription', AsyncMock())
    monkeypatch.setattr(auto_module, 'clear_subscription_checkout_draft', AsyncMock())
    monkeypatch.setattr(auto_module, '_notify_email_user_auto_purchase', AsyncMock())
    monkeypatch.setattr(renewal_module, 'with_admin_notification_service', AsyncMock())
    for name in ('notify_user_subscription_renewed', 'notify_user_subscription_activated'):
        monkeypatch.setattr(websocket, name, AsyncMock())
    return auto_module


async def _seed_auto(db, *, balance_toman: int, expired: bool = False, with_subscription: bool = True) -> None:
    from datetime import UTC, datetime, timedelta

    await _seed(db, balance_toman=balance_toman, with_subscription=with_subscription)
    await _add_daily_tariff(db)
    if expired:
        subscription = await db.get(Subscription, 10)
        now = datetime.now(UTC)
        subscription.status = 'expired'
        subscription.autopay_enabled = True
        subscription.end_date = now - timedelta(days=2)
        subscription.updated_at = now - timedelta(days=2)
        await db.commit()


AUTO_FLOWS = {
    # name: (function, cart, seed kwargs)
    'extend': (
        '_auto_extend_subscription',
        {'cart_mode': 'extend', 'subscription_id': 10, 'tariff_id': 1, 'period_days': 30},
        {},
    ),
    'tariff': ('_auto_purchase_tariff', {'cart_mode': 'tariff_purchase', 'tariff_id': 2, 'period_days': 30}, {}),
    'daily tariff': (
        '_auto_purchase_daily_tariff',
        {'cart_mode': 'daily_tariff_purchase', 'tariff_id': 3},
        {'with_subscription': False},
    ),
    'expired renewal': ('try_auto_extend_expired_after_topup', None, {'expired': True}),
}


async def _run_auto(auto, flow: str, db) -> bool:
    name, cart, _ = AUTO_FLOWS[flow]
    user = await _loaded_user(db)
    if cart is None:
        return await getattr(auto, name)(db, user)
    return await getattr(auto, name)(db, user, dict(cart))


@pytest.mark.parametrize('flow', sorted(AUTO_FLOWS))
@pytest.mark.asyncio
async def test_auto_purchase_waits_for_a_balance_that_covers_the_toman_price(monkeypatch, auto, flow):
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_auto(db, balance_toman=SHORT_BALANCE, **AUTO_FLOWS[flow][2])
        assert await _run_auto(auto, flow, db) is False
        assert await _balance(db) == SHORT_BALANCE
        assert await _payments(db) == []


@pytest.mark.parametrize('flow', sorted(AUTO_FLOWS))
@pytest.mark.asyncio
async def test_auto_purchase_debits_the_toman_price(monkeypatch, auto, flow):
    import app.database.crud.user as user_crud

    # module-level import (extend, expired renewal) and function-local imports (tariff, daily tariff)
    debits = _spy_debits(monkeypatch, auto), _spy_debits(monkeypatch, user_crud)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_auto(db, balance_toman=RICH_BALANCE, **AUTO_FLOWS[flow][2])
        assert await _run_auto(auto, flow, db) is True
        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]
    assert debits[0] + debits[1] == [PRICE_TOMAN]


AUTO_FAILURES = {
    # flow: (module holding the creation step, its name)
    'extend': ('app.services.subscription_auto_purchase_service', 'extend_subscription'),
    'tariff': ('app.database.crud.subscription', 'extend_subscription'),
    'daily tariff': ('app.database.crud.subscription', 'create_paid_subscription'),
    'expired renewal': ('app.services.subscription_auto_purchase_service', 'extend_subscription'),
}


@pytest.mark.parametrize('flow', sorted(AUTO_FLOWS))
@pytest.mark.asyncio
async def test_auto_purchase_refunds_the_toman_price_when_the_subscription_step_fails(monkeypatch, auto, flow):
    """The refund runs after db.rollback(), which expires the user it is handed."""
    import importlib

    module_name, name = AUTO_FAILURES[flow]
    monkeypatch.setattr(importlib.import_module(module_name), name, AsyncMock(side_effect=RuntimeError('db down')))
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_auto(db, balance_toman=RICH_BALANCE, **AUTO_FLOWS[flow][2])
        assert await _run_auto(auto, flow, db) is False
        assert await _balance(db) == RICH_BALANCE
        assert await _payments(db) == [('refund', PRICE_TOMAN)]


@pytest.mark.asyncio
async def test_auto_daily_tariff_message_shows_the_toman_price(monkeypatch, auto):
    monkeypatch.setattr(Settings, 'is_notifications_enabled', lambda self: True)
    bot = SimpleNamespace(send_message=AsyncMock())
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_auto(db, balance_toman=RICH_BALANCE, with_subscription=False)
        assert await auto._auto_purchase_daily_tariff(db, await _loaded_user(db), {'tariff_id': 3}, bot=bot)

    text = bot.send_message.await_args.kwargs['text']
    assert settings.format_price(PRICE_KOPEKS) in text  # «200,000 تومان»
    assert '₽' not in text
    assert 'روزانه' in text  # the fa locale, not the old hard-coded Russian


@pytest.mark.parametrize('balance', [SHORT_BALANCE, RICH_BALANCE])
@pytest.mark.asyncio
async def test_auto_legacy_cart_gates_on_the_toman_price(monkeypatch, auto, balance):
    from tests.services.test_affordability_toman import _purchase_pricing

    service = SimpleNamespace(submit_purchase=AsyncMock(side_effect=RuntimeError('stop after the gate')))
    prepared = SimpleNamespace(pricing=_purchase_pricing(), selection=None, context=None, service=service)
    monkeypatch.setattr(auto, '_prepare_auto_purchase', AsyncMock(return_value=prepared))
    user = SimpleNamespace(id=1, telegram_id=1001, balance_kopeks=balance)

    assert await auto._process_legacy_generic_cart(None, user, {'period_days': 30}) is False
    # the submit (which debits the Toman price since #36) is reached only when the balance covers it
    assert service.submit_purchase.await_count == (1 if balance == RICH_BALANCE else 0)


# ---------------------------------------------------------------- cabinet: add countries (classic mode)


def _cabinet_countries(monkeypatch):
    import app.database.crud.server_squad as squad_crud
    import app.database.crud.subscription as subscription_crud
    from app.cabinet.routes.subscription_modules import servers
    from app.utils import pricing_utils

    async def resolve(db, user, subscription_id):
        return await db.get(Subscription, 10)

    squads = [
        SimpleNamespace(squad_uuid='squad-1', price_kopeks=0, display_name='NL'),
        SimpleNamespace(squad_uuid='squad-2', price_kopeks=PRICE_KOPEKS, display_name='DE'),
    ]
    monkeypatch.setattr(servers, 'resolve_subscription', resolve)
    monkeypatch.setattr(servers, 'SubscriptionService', lambda: _FakePanelSync())
    monkeypatch.setattr(squad_crud, 'get_available_server_squads', AsyncMock(return_value=squads))
    monkeypatch.setattr(squad_crud, 'get_server_ids_by_uuids', AsyncMock(return_value=[2]))
    monkeypatch.setattr(squad_crud, 'add_user_to_servers', AsyncMock())
    monkeypatch.setattr(subscription_crud, 'add_subscription_servers', AsyncMock())
    monkeypatch.setattr(pricing_utils, 'calculate_prorated_price', lambda price, end_date, *a, **k: (price, 30))
    return servers


@pytest.mark.asyncio
async def test_cabinet_add_countries_refuses_with_the_toman_shortfall_then_debits_the_toman_price(monkeypatch):
    from fastapi import HTTPException

    servers = _cabinet_countries(monkeypatch)
    request = {'countries': ['squad-1', 'squad-2']}

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE)
        with pytest.raises(HTTPException) as caught:
            await servers.update_countries(request=request, user=await _loaded_user(db), db=db, subscription_id=None)
        assert await _balance(db) == SHORT_BALANCE

    assert caught.value.status_code == 402
    assert caught.value.detail['missing_amount'] == SHORTFALL_TOMAN  # Toman, like every 402 since #27
    assert SHORTFALL_LABEL in caught.value.detail['message']  # the cabinet shows detail.message
    assert 'RUB' not in caught.value.detail['message']

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        response = await servers.update_countries(
            request=request, user=await _loaded_user(db), db=db, subscription_id=None
        )

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]
    assert response['amount_paid_kopeks'] == PRICE_KOPEKS  # catalog, like every *_kopeks price field


# ---------------------------------------------------------------- bot simple subscription (SIMPLE_SUBSCRIPTION_ENABLED)


SIMPLE_PARAMS = {'period_days': 30, 'device_limit': 1, 'traffic_limit_gb': 0, 'squad_uuid': 'squad-1'}


@pytest.fixture
def simple(monkeypatch):
    import app.services.subscription_service as subscription_service_module
    from app.handlers import simple_subscription
    from app.handlers.subscription import purchase

    price = AsyncMock(return_value=(PRICE_KOPEKS, {}))
    monkeypatch.setattr(settings, 'SIMPLE_SUBSCRIPTION_ENABLED', True, raising=False)
    monkeypatch.setattr(simple_subscription, '_calculate_simple_subscription_price', price)
    monkeypatch.setattr(purchase, '_calculate_simple_subscription_price', price)
    monkeypatch.setattr(
        simple_subscription, '_ensure_simple_subscription_squad_uuid', AsyncMock(return_value='squad-1')
    )
    monkeypatch.setattr(subscription_service_module, 'SubscriptionService', lambda: _FakePanelSync())
    return simple_subscription


def _simple_state() -> SimpleNamespace:
    return _state({'subscription_params': dict(SIMPLE_PARAMS)})


SIMPLE_SCREENS = {
    'start': ('app.handlers.simple_subscription', 'start_simple_subscription_purchase'),
    'other methods': ('app.handlers.simple_subscription', 'handle_simple_subscription_other_payment_methods'),
    'purchase menu': ('app.handlers.subscription.purchase', 'handle_simple_subscription_purchase'),
}


@pytest.mark.parametrize('screen', sorted(SIMPLE_SCREENS))
@pytest.mark.parametrize('balance', [SHORT_BALANCE, RICH_BALANCE])
@pytest.mark.asyncio
async def test_simple_subscription_offers_pay_from_balance_only_when_the_toman_balance_covers_it(
    monkeypatch, simple, screen, balance
):
    import importlib

    module_name, name = SIMPLE_SCREENS[screen]
    handler = getattr(importlib.import_module(module_name), name)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=balance, with_subscription=False)
        callback = _callback('simple_subscription')
        if screen == 'purchase menu':
            await handler(callback, _simple_state(), await _loaded_user(db), db)
        else:
            await handler(callback, await _loaded_user(db), _simple_state(), db)

    offered = 'simple_subscription_pay_with_balance' in _buttons(callback)
    assert offered is (balance == RICH_BALANCE)


SIMPLE_PAYMENTS = {
    # handler, with an existing (active, paid) subscription
    'pay with balance': ('handle_simple_subscription_pay_with_balance', False),
    'confirm over an active subscription': ('confirm_simple_subscription_purchase', True),
}


@pytest.mark.parametrize('flow', sorted(SIMPLE_PAYMENTS))
@pytest.mark.asyncio
async def test_simple_subscription_payment_refuses_then_debits_the_toman_price(monkeypatch, simple, flow):
    name, with_subscription = SIMPLE_PAYMENTS[flow]
    handler = getattr(simple, name)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE, with_subscription=with_subscription)
        refused = _callback('pay')
        await handler(refused, await _loaded_user(db), _simple_state(), db)
        assert await _balance(db) == SHORT_BALANCE

    assert 'Недостаточно средств' in refused.answer.await_args.args[0]

    debits = _spy_debits(monkeypatch, __import__('app.database.crud.user', fromlist=['x']))
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE, with_subscription=with_subscription)
        await handler(_callback('pay'), await _loaded_user(db), _simple_state(), db)

        assert debits == [PRICE_TOMAN]
        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]


@pytest.mark.parametrize('flow', sorted(SIMPLE_PAYMENTS))
@pytest.mark.asyncio
async def test_simple_subscription_refunds_the_toman_price_when_no_subscription_comes_back(monkeypatch, simple, flow):
    import app.database.crud.subscription as subscription_crud

    name, _ = SIMPLE_PAYMENTS[flow]
    # without a subscription both handlers create one; a None result is refunded
    monkeypatch.setattr(subscription_crud, 'create_paid_subscription', AsyncMock(return_value=None))
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE, with_subscription=False)
        callback = _callback('pay')
        await getattr(simple, name)(callback, await _loaded_user(db), _simple_state(), db)

        assert await _balance(db) == RICH_BALANCE
        assert sorted(await _payments(db)) == [('refund', PRICE_TOMAN), ('subscription_payment', PRICE_KOPEKS)]
    assert 'Средства возвращены' in callback.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_simple_subscription_extension_refunds_the_toman_price_when_the_commit_fails(monkeypatch, simple):
    """purchase._extend_existing_subscription: the refund after db.rollback() returned the catalog price."""
    from app.handlers.subscription import purchase

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        real_commit = db.commit
        calls = {'n': 0}

        async def commit():
            calls['n'] += 1
            if calls['n'] == 2:  # 1: the debit, 2: the extension, 3: the refund
                raise RuntimeError('commit failed')
            await real_commit()

        monkeypatch.setattr(db, 'commit', commit)
        callback = _callback('simple_subscription_purchase')
        await purchase._extend_existing_subscription(
            callback, await _loaded_user(db), db, await db.get(Subscription, 10), 30, 1, 0, 'squad-1'
        )

        assert await _balance(db) == RICH_BALANCE
        assert await _payments(db) == [('refund', PRICE_TOMAN)]
