"""Balance checks, shortfalls and debits compare the Toman balance with the Toman price.

These paths once mixed two scales: ``User.balance_kopeks`` was raw Toman while tariff prices, switch
costs, server and traffic prices and the trial activation price were catalog ``price_kopeks``
(Toman x 100). Comparing them directly reported ``price - balance`` as the shortfall and debited the
catalog number, so a 200,000-Toman tariff switch needed — and took — 20,000,000 Toman.

Revision ``0115`` moved the catalog columns onto the Toman scale, so there is no conversion left to
get wrong: a price, a balance and a ledger row are all the same kind of number. What this file still
does is pin every surface with the same figures, which is what makes a regression at any one of them
visible.

A 150,000-Toman balance against a 200,000-Toman price is refused with a 50,000-Toman shortfall; a
250,000-Toman balance gets exactly 200,000 debited and the ledger row reads -200,000.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import Settings, settings
from app.database.models import Base, Subscription, SubscriptionStatus, Tariff, Transaction, User
from app.services.pricing_engine import PricingEngine, TariffSwitchResult
from tests.fixtures.sqlite_memory import memory_session


TABLES = list(Base.metadata.sorted_tables)

# Since Phase C the stored price *is* the Toman price; the name is kept so the call sites that
# read as "the catalog column" still say so.
PRICE_TOMAN = 200_000
PRICE_KOPEKS = PRICE_TOMAN
SHORT_BALANCE = 150_000
SHORTFALL_TOMAN = 50_000
RICH_BALANCE = 250_000

SHORTFALL_LABEL = settings.format_balance(SHORTFALL_TOMAN)  # «50,000 تومان»


class _FakePanelSync:
    async def update_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def create_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def sync_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """No panel, Redis, admin bot or multi-tariff branching; tariffs mode like the live env."""
    import app.database.crud.transaction as transaction_crud
    import app.services.pricing_engine as pricing_module
    import app.services.yandex_offline_conv_service as yandex_conv
    from app.services.payment import lava, platega
    from app.services.user_cart_service import user_cart_service

    # Other modules patch these on the pricing_engine singleton instance and monkeypatch restores them as
    # instance attributes, which would shadow the class-level patches used here.
    for name in ('calculate_tariff_switch_cost', 'calculate_tariff_purchase_price'):
        pricing_module.pricing_engine.__dict__.pop(name, None)
    monkeypatch.setattr(settings, 'ADMIN_NOTIFICATIONS_ENABLED', False, raising=False)
    monkeypatch.setattr(settings, 'RESET_TRAFFIC_ON_PAYMENT', False, raising=False)
    monkeypatch.setattr(settings, 'TARIFF_SWITCH_UPGRADE_ENABLED', True, raising=False)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    monkeypatch.setattr(Settings, 'is_tariffs_mode', lambda self: True)
    monkeypatch.setattr(user_cart_service, 'save_user_cart', AsyncMock(return_value=True))
    monkeypatch.setattr(yandex_conv, 'store_cid_only', AsyncMock(return_value=None))
    monkeypatch.setattr(platega, 'cancel_platega_recurring_for_subscription_safe', AsyncMock())
    monkeypatch.setattr(lava, 'cancel_lava_recurring_for_subscription_safe', AsyncMock())
    monkeypatch.setattr(transaction_crud, 'emit_transaction_side_effects', AsyncMock())


def _switch_cost(monkeypatch, upgrade_cost: int = PRICE_KOPEKS) -> None:
    def fake(self, current_tariff, new_tariff, remaining_days, *, user=None):
        return TariffSwitchResult(
            upgrade_cost=upgrade_cost,
            is_upgrade=True,
            raw_cost=upgrade_cost,
            group_discount_pct=0,
            offer_discount_pct=0,
        )

    monkeypatch.setattr(PricingEngine, 'calculate_tariff_switch_cost', fake)


def _tariff(tariff_id: int, name: str, price_kopeks: int) -> Tariff:
    return Tariff(
        id=tariff_id,
        name=name,
        description='',
        is_active=True,
        is_daily=False,
        period_prices={'30': price_kopeks},
        traffic_limit_gb=100,
        traffic_reset_mode='NO_RESET',
        device_limit=1,
        max_device_limit=10,
        device_price_kopeks=100,
        allowed_squads=['squad-1'],
        display_order=tariff_id,
    )


async def _seed(db, *, balance_toman: int, with_subscription: bool = True) -> User:
    now = datetime.now(UTC)
    rows: list = [
        User(id=1, telegram_id=1001, first_name='U', language='fa', status='active', balance_kopeks=balance_toman),
        _tariff(1, 'basic', 10_000_000),
        _tariff(2, 'premium', 30_000_000),
    ]
    if with_subscription:
        rows.append(
            Subscription(
                id=10,
                remnawave_short_id='aff1',
                user_id=1,
                status=SubscriptionStatus.ACTIVE.value,
                is_trial=False,
                start_date=now - timedelta(days=1),
                end_date=now + timedelta(days=20),
                updated_at=now - timedelta(hours=1),
                traffic_limit_gb=100,
                traffic_used_gb=1.0,
                purchased_traffic_gb=0,
                device_limit=1,
                tariff_id=1,
                connected_squads=['squad-1'],
            )
        )
    db.add_all(rows)
    await db.commit()
    return await db.get(User, 1)


async def _loaded_user(db) -> User:
    """User 1 with subscriptions eager-loaded, as the bot middleware hands it to handlers."""
    from app.database.crud.user import lock_user_for_pricing

    return await lock_user_for_pricing(db, 1)


async def _balance(db) -> int:
    return (await db.execute(select(User.balance_kopeks).where(User.id == 1))).scalar_one()


async def _payments(db) -> list[tuple[str, int]]:
    result = await db.execute(select(Transaction.type, Transaction.amount_kopeks).where(Transaction.user_id == 1))
    return [(tx_type, abs(amount)) for tx_type, amount in result.all()]


async def _tariff_id(db) -> int:
    return (await db.execute(select(Subscription.tariff_id).where(Subscription.id == 10))).scalar_one()


# ---------------------------------------------------------------- cabinet: tariff switch


def _cabinet_switch_request():
    from app.cabinet.schemas.subscription import TariffPurchaseRequest

    return TariffPurchaseRequest(tariff_id=2, period_days=30)


@pytest.mark.asyncio
async def test_cabinet_switch_preview_refuses_with_the_toman_shortfall(monkeypatch):
    from app.cabinet.routes.subscription_modules import tariff_switch

    _switch_cost(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=SHORT_BALANCE)
        response = await tariff_switch.preview_tariff_switch(
            request=_cabinet_switch_request(), user=user, db=db, subscription_id=None
        )

    assert response['can_switch'] is False
    assert response['has_enough_balance'] is False
    # The cabinet's InsufficientBalancePrompt reads this field on the catalog scale (÷100 for the
    # label and the prefilled top-up), so it carries the Toman shortfall x 100.
    assert response['missing_amount_kopeks'] == SHORTFALL_TOMAN * 100
    assert response['missing_amount_label'] == SHORTFALL_LABEL


@pytest.mark.asyncio
async def test_cabinet_switch_preview_allows_a_balance_covering_the_toman_price(monkeypatch):
    from app.cabinet.routes.subscription_modules import tariff_switch

    _switch_cost(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=RICH_BALANCE)
        response = await tariff_switch.preview_tariff_switch(
            request=_cabinet_switch_request(), user=user, db=db, subscription_id=None
        )

    assert response['can_switch'] is True
    assert response['missing_amount_kopeks'] == 0
    # Same wire contract as the shortfall above: the cabinet divides this field by 100.
    assert response['upgrade_cost_kopeks'] == PRICE_TOMAN * 100


@pytest.mark.asyncio
async def test_cabinet_switch_refuses_with_the_toman_shortfall(monkeypatch):
    from app.cabinet.routes.subscription_modules import tariff_switch

    _switch_cost(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=SHORT_BALANCE)
        with pytest.raises(HTTPException) as caught:
            await tariff_switch.switch_tariff(request=_cabinet_switch_request(), user=user, db=db, subscription_id=None)

        assert await _balance(db) == SHORT_BALANCE
        assert await _tariff_id(db) == 1

    assert caught.value.status_code == 402
    assert caught.value.detail['missing_amount'] == SHORTFALL_TOMAN  # Toman, like every 402 since #27
    assert SHORTFALL_LABEL in caught.value.detail['message']


@pytest.mark.asyncio
async def test_cabinet_switch_debits_the_toman_price(monkeypatch):
    from app.cabinet.routes.subscription_modules import tariff_switch

    monkeypatch.setattr(tariff_switch, 'SubscriptionService', lambda: _FakePanelSync())
    _switch_cost(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=RICH_BALANCE)
        await tariff_switch.switch_tariff(request=_cabinet_switch_request(), user=user, db=db, subscription_id=None)

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]
        assert await _tariff_id(db) == 2


# ---------------------------------------------------------------- miniapp


@pytest.fixture
def miniapp_user(monkeypatch):
    """Authorize as user 1 with subscriptions loaded, like _authorize_miniapp_user does."""
    from app.database.crud.user import lock_user_for_pricing
    from app.webapi.routes import miniapp

    async def authorize(init_data, db):
        return await lock_user_for_pricing(db, 1)

    monkeypatch.setattr(miniapp, '_authorize_miniapp_user', authorize)
    monkeypatch.setattr(miniapp, 'SubscriptionService', lambda: _FakePanelSync(), raising=False)
    return miniapp


def _miniapp_switch_cost(monkeypatch, miniapp) -> None:
    def fake(current_tariff, new_tariff, remaining_days, user=None):
        return TariffSwitchResult(
            upgrade_cost=PRICE_KOPEKS,
            is_upgrade=True,
            raw_cost=PRICE_KOPEKS,
            group_discount_pct=0,
            offer_discount_pct=0,
        )

    monkeypatch.setattr(miniapp, '_calculate_tariff_switch', fake)


@pytest.mark.asyncio
async def test_miniapp_switch_preview_reports_the_toman_shortfall(monkeypatch, miniapp_user):
    from app.webapi.schemas.miniapp import MiniAppTariffSwitchRequest

    _miniapp_switch_cost(monkeypatch, miniapp_user)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE)
        short = await miniapp_user.preview_tariff_switch_endpoint(
            MiniAppTariffSwitchRequest(init_data='x', tariff_id=2), db=db
        )
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        rich = await miniapp_user.preview_tariff_switch_endpoint(
            MiniAppTariffSwitchRequest(init_data='x', tariff_id=2), db=db
        )

    assert short.can_switch is False
    assert short.missing_amount_kopeks == SHORTFALL_TOMAN  # miniapp shortfalls are Toman (#26)
    assert short.missing_amount_label == SHORTFALL_LABEL
    assert rich.can_switch is True
    assert rich.missing_amount_kopeks == 0


@pytest.mark.asyncio
async def test_miniapp_switch_refuses_then_debits_the_toman_price(monkeypatch, miniapp_user):
    from app.webapi.schemas.miniapp import MiniAppTariffSwitchRequest

    _miniapp_switch_cost(monkeypatch, miniapp_user)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE)
        with pytest.raises(HTTPException) as caught:
            await miniapp_user.switch_tariff_endpoint(MiniAppTariffSwitchRequest(init_data='x', tariff_id=2), db=db)
        assert await _balance(db) == SHORT_BALANCE

    assert caught.value.status_code == 402
    assert caught.value.detail['missing_amount'] == SHORTFALL_TOMAN
    assert SHORTFALL_LABEL in caught.value.detail['message']

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        await miniapp_user.switch_tariff_endpoint(MiniAppTariffSwitchRequest(init_data='x', tariff_id=2), db=db)

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]
        assert await _tariff_id(db) == 2


def _tariff_purchase_price(monkeypatch) -> None:
    async def fake(self, tariff, period_days, *, device_limit=None, user=None, **kwargs):
        return SimpleNamespace(final_total=PRICE_KOPEKS, promo_offer_discount=0, breakdown={})

    monkeypatch.setattr(PricingEngine, 'calculate_tariff_purchase_price', fake)


@pytest.mark.asyncio
async def test_miniapp_tariff_purchase_refuses_then_debits_the_toman_price(monkeypatch, miniapp_user):
    from app.webapi.schemas.miniapp import MiniAppTariffPurchaseRequest

    _tariff_purchase_price(monkeypatch)
    request = {'initData': 'x', 'tariffId': 2, 'periodDays': 30}
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE, with_subscription=False)
        with pytest.raises(HTTPException) as caught:
            await miniapp_user.purchase_tariff_endpoint(MiniAppTariffPurchaseRequest(**request), db=db)
        assert await _balance(db) == SHORT_BALANCE

    assert caught.value.status_code == 402
    assert caught.value.detail['missing_amount'] == SHORTFALL_TOMAN
    assert SHORTFALL_LABEL in caught.value.detail['message']

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE, with_subscription=False)
        await miniapp_user.purchase_tariff_endpoint(MiniAppTariffPurchaseRequest(**request), db=db)

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert ('subscription_payment', PRICE_KOPEKS) in await _payments(db)


def _server_catalog(monkeypatch, miniapp) -> None:
    catalog = {
        'squad-1': {'server_id': 1, 'discounted_per_month': 0, 'available_for_new': True, 'name': 'NL'},
        'squad-2': {'server_id': 2, 'discounted_per_month': PRICE_KOPEKS, 'available_for_new': True, 'name': 'DE'},
    }
    monkeypatch.setattr(miniapp, '_prepare_server_catalog', AsyncMock(return_value=([], [], catalog)))
    monkeypatch.setattr(
        miniapp,
        'get_available_server_squads',
        AsyncMock(return_value=[SimpleNamespace(squad_uuid='squad-1'), SimpleNamespace(squad_uuid='squad-2')]),
    )
    monkeypatch.setattr(miniapp, 'calculate_prorated_price', lambda *args, **kwargs: (PRICE_KOPEKS, 30))
    monkeypatch.setattr(miniapp, 'add_subscription_servers', AsyncMock())
    monkeypatch.setattr(miniapp, 'remove_subscription_servers', AsyncMock(), raising=False)
    monkeypatch.setattr(miniapp, 'update_server_user_counts', AsyncMock(), raising=False)
    monkeypatch.setattr(miniapp, '_validate_subscription_id', lambda *args, **kwargs: None)


@pytest.mark.asyncio
async def test_miniapp_server_add_refuses_then_debits_the_toman_price(monkeypatch, miniapp_user):
    from app.webapi.schemas.miniapp import MiniAppSubscriptionServersUpdateRequest

    _server_catalog(monkeypatch, miniapp_user)
    request = {'initData': 'x', 'subscription_id': 10, 'servers': ['squad-1', 'squad-2']}
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE)
        with pytest.raises(HTTPException) as caught:
            await miniapp_user.update_subscription_servers_endpoint(
                MiniAppSubscriptionServersUpdateRequest(**request), db=db
            )
        assert await _balance(db) == SHORT_BALANCE

    assert caught.value.status_code == 402
    assert caught.value.detail['missing_amount'] == SHORTFALL_TOMAN
    assert SHORTFALL_LABEL in caught.value.detail['message']

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        await miniapp_user.update_subscription_servers_endpoint(
            MiniAppSubscriptionServersUpdateRequest(**request), db=db
        )

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]


# ---------------------------------------------------------------- purchase service (cabinet + miniapp preview)


def _purchase_pricing():
    from app.services.subscription_purchase_service import PurchasePricingResult, PurchaseSelection

    period = SimpleNamespace(id='days:30', days=30, months=1)
    return PurchasePricingResult(
        selection=PurchaseSelection(period=period, traffic_value=100, servers=['squad-1'], devices=1),
        server_ids=[],
        server_prices_for_period=[],
        base_original_total=PRICE_KOPEKS,
        discounted_total=PRICE_KOPEKS,
        promo_discount_value=0,
        promo_discount_percent=0,
        final_total=PRICE_KOPEKS,
        months=1,
        details={},
    )


def test_purchase_preview_reports_the_toman_shortfall_on_the_cabinet_scale():
    from app.services.subscription_purchase_service import MiniAppSubscriptionPurchaseService

    service = MiniAppSubscriptionPurchaseService()
    user = SimpleNamespace(language='fa')
    short = service.build_preview_payload(SimpleNamespace(user=user, balance_kopeks=SHORT_BALANCE), _purchase_pricing())
    rich = service.build_preview_payload(SimpleNamespace(user=user, balance_kopeks=RICH_BALANCE), _purchase_pricing())

    assert short['can_purchase'] is False
    # ClassicPurchaseWizard hands missing_amount_kopeks to InsufficientBalancePrompt (catalog scale, ÷100)
    assert short['missing_amount_kopeks'] == SHORTFALL_TOMAN * 100
    assert short['missing_amount_label'] == SHORTFALL_LABEL
    assert rich['can_purchase'] is True
    assert rich['missing_amount_kopeks'] == 0


@pytest.mark.asyncio
async def test_purchase_submit_refuses_then_debits_the_toman_price(monkeypatch):
    import app.services.subscription_purchase_service as purchase_module
    from app.services.subscription_purchase_service import MiniAppSubscriptionPurchaseService, PurchaseBalanceError

    monkeypatch.setattr(purchase_module, 'SubscriptionService', lambda: _FakePanelSync())
    service = MiniAppSubscriptionPurchaseService()

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=SHORT_BALANCE)
        subscription = await db.get(Subscription, 10)
        context = SimpleNamespace(user=user, subscription=subscription, payload={}, balance_kopeks=SHORT_BALANCE)
        with pytest.raises(PurchaseBalanceError):
            await service.submit_purchase(db, context, _purchase_pricing())
        assert await _balance(db) == SHORT_BALANCE

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=RICH_BALANCE)
        subscription = await db.get(Subscription, 10)
        context = SimpleNamespace(user=user, subscription=subscription, payload={}, balance_kopeks=RICH_BALANCE)
        await service.submit_purchase(db, context, _purchase_pricing())

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]


# ---------------------------------------------------------------- paid trial


@pytest.fixture
def paid_trial(monkeypatch):
    monkeypatch.setattr(Settings, 'is_trial_paid_activation_enabled', lambda self: True)
    monkeypatch.setattr(Settings, 'get_trial_activation_price', lambda self: PRICE_KOPEKS)
    monkeypatch.setattr(settings, 'TRIAL_PAYMENT_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'TRIAL_ACTIVATION_PRICE', PRICE_KOPEKS, raising=False)


def _spy_debits(monkeypatch, module) -> list[int]:
    """Record what a module passes to subtract_user_balance, then run the real debit."""
    debits: list[int] = []
    real = module.subtract_user_balance

    async def spy(db, user, amount, *args, **kwargs):
        debits.append(amount)
        return await real(db, user, amount, *args, **kwargs)

    monkeypatch.setattr(module, 'subtract_user_balance', spy)
    return debits


@pytest.mark.asyncio
async def test_trial_service_reports_the_toman_shortfall(monkeypatch, paid_trial):
    from app.services.trial_activation_service import TrialPaymentInsufficientFunds, preview_trial_activation_charge

    with pytest.raises(TrialPaymentInsufficientFunds) as caught:
        preview_trial_activation_charge(SimpleNamespace(balance_kopeks=SHORT_BALANCE))

    assert caught.value.missing_amount == SHORTFALL_TOMAN  # also the miniapp 402 missing_amount_kopeks
    assert preview_trial_activation_charge(SimpleNamespace(balance_kopeks=RICH_BALANCE)) == PRICE_KOPEKS


@pytest.mark.asyncio
async def test_trial_service_debits_and_refunds_the_toman_price(monkeypatch, paid_trial):
    from app.services import trial_activation_service as trial

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=RICH_BALANCE, with_subscription=False)
        charged = await trial.charge_trial_activation_if_required(db, user)

        assert charged == PRICE_KOPEKS  # the Toman price callers display with format_balance
        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]

        await trial.revert_trial_activation(db, user, None, charged)

        assert await _balance(db) == RICH_BALANCE
        assert ('refund', PRICE_TOMAN) in await _payments(db)


def _trial_callback() -> SimpleNamespace:
    return SimpleNamespace(
        data='trial_pay_with_balance',
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_bot_trial_pay_refuses_with_the_toman_shortfall(monkeypatch, paid_trial):
    from app.handlers.subscription import purchase

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE, with_subscription=False)
        user = await _loaded_user(db)
        callback = _trial_callback()
        await purchase.handle_trial_pay_with_balance(callback, user, db)

        assert await _balance(db) == SHORT_BALANCE

    alert = callback.answer.await_args.args[0]
    assert SHORTFALL_LABEL in alert


@pytest.mark.asyncio
async def test_bot_trial_pay_debits_the_toman_price_and_refunds_it_on_failure(monkeypatch, paid_trial):
    from app.handlers.subscription import purchase

    debits = _spy_debits(monkeypatch, purchase)
    monkeypatch.setattr(purchase, 'create_trial_subscription', AsyncMock(side_effect=RuntimeError('panel down')))
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE, with_subscription=False)
        user = await _loaded_user(db)
        await purchase.handle_trial_pay_with_balance(_trial_callback(), user, db)

        assert debits == [PRICE_TOMAN]
        # the activation failed after the debit: the Toman amount comes back as a refund row
        assert await _balance(db) == RICH_BALANCE
        assert sorted(await _payments(db)) == [('refund', PRICE_TOMAN), ('subscription_payment', PRICE_KOPEKS)]


@pytest.mark.asyncio
async def test_cabinet_trial_refuses_with_the_toman_shortfall_then_debits_the_toman_price(monkeypatch, paid_trial):
    from app.cabinet.routes.subscription_modules import purchase as cabinet_purchase

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=SHORT_BALANCE, with_subscription=False)
        with pytest.raises(HTTPException) as caught:
            await cabinet_purchase.activate_trial(user=user, db=db)
        assert await _balance(db) == SHORT_BALANCE

    assert SHORTFALL_LABEL in caught.value.detail

    debits = _spy_debits(monkeypatch, __import__('app.database.crud.user', fromlist=['x']))
    monkeypatch.setattr(cabinet_purchase, 'create_trial_subscription', AsyncMock(side_effect=RuntimeError('stop')))
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=RICH_BALANCE, with_subscription=False)
        with pytest.raises(Exception):  # noqa: B017 - activation is stopped right after the debit
            await cabinet_purchase.activate_trial(user=user, db=db)

        assert debits == [PRICE_TOMAN]
        assert ('subscription_payment', PRICE_KOPEKS) in await _payments(db)


# ---------------------------------------------------------------- bot: countries and traffic reset


def _bot_callback(data: str) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        from_user=SimpleNamespace(id=1001),
    )


def _sent_text(callback) -> str:
    for mock in (callback.message.edit_text, callback.message.answer):
        if mock.await_args is not None:
            return mock.await_args.args[0]
    return ''


def _prefill(monkeypatch, module) -> list[int]:
    """Capture the amount the insufficient-balance keyboard prefills (it expects Toman)."""
    amounts: list[int] = []

    def keyboard(language, *args, amount_kopeks=None, **kwargs):
        amounts.append(amount_kopeks)

    monkeypatch.setattr(module, 'get_insufficient_balance_keyboard', keyboard)
    return amounts


def _countries_setup(monkeypatch):
    from app.handlers.subscription import countries

    async def resolve(callback, db_user, db, state=None):
        return await db.get(Subscription, 10), 10

    available = [
        {'uuid': 'squad-1', 'name': 'NL', 'price_kopeks': 0, 'is_available': True, 'id': 1},
        {'uuid': 'squad-2', 'name': 'DE', 'price_kopeks': PRICE_KOPEKS, 'is_available': True, 'id': 2},
    ]
    monkeypatch.setattr(countries, '_resolve_subscription', resolve)
    monkeypatch.setattr(countries, '_get_available_countries', AsyncMock(return_value=available))
    monkeypatch.setattr(countries, 'calculate_prorated_price', lambda price, end_date, *a, **k: (price, 30))
    monkeypatch.setattr(countries, 'save_subscription_checkout_draft', AsyncMock(), raising=False)
    monkeypatch.setattr(countries, 'get_server_ids_by_uuids', AsyncMock(return_value=[2]), raising=False)
    monkeypatch.setattr(countries, 'add_subscription_servers', AsyncMock(), raising=False)
    monkeypatch.setattr(countries, 'add_user_to_servers', AsyncMock(), raising=False)
    monkeypatch.setattr(countries, 'SubscriptionService', lambda: _FakePanelSync(), raising=False)
    state = SimpleNamespace(get_data=AsyncMock(return_value={'countries': ['squad-1', 'squad-2']}), clear=AsyncMock())
    return countries, state


@pytest.mark.parametrize('handler', ['apply_countries_changes', 'confirm_add_countries_to_subscription'])
@pytest.mark.asyncio
async def test_bot_countries_refuse_with_the_toman_shortfall_then_debit_the_toman_price(monkeypatch, handler):
    countries, state = _countries_setup(monkeypatch)
    prefill = _prefill(monkeypatch, countries)
    run = getattr(countries, handler)

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE)
        callback = _bot_callback('x')
        await run(callback, await _loaded_user(db), db, state)
        assert await _balance(db) == SHORT_BALANCE

    assert SHORTFALL_LABEL in _sent_text(callback)
    assert prefill == [SHORTFALL_TOMAN]  # Toman top-up prefill (rounded to the 1,000 step)

    debits = _spy_debits(monkeypatch, countries)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        await run(_bot_callback('x'), await _loaded_user(db), db, state)

        assert debits == [PRICE_TOMAN]
        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]


class _FakeRemnaWave:
    def __init__(self):
        self.api = SimpleNamespace(reset_user_traffic=AsyncMock(), get_user_by_short_uuid=AsyncMock(return_value=None))

    def get_api_client(self):
        service = self

        class _Ctx:
            async def __aenter__(self):
                return service.api

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


def _traffic_setup(monkeypatch):
    from app.handlers.subscription import traffic

    async def resolve(callback, db_user, db, state=None):
        return await db.get(Subscription, 10), 10

    monkeypatch.setattr(Settings, 'is_traffic_topup_blocked', lambda self: False)
    monkeypatch.setattr(traffic, '_resolve_subscription', resolve)
    monkeypatch.setattr(traffic, '_calculate_traffic_reset_price', lambda subscription: PRICE_KOPEKS)
    monkeypatch.setattr(traffic, 'RemnaWaveService', _FakeRemnaWave)
    return traffic


@pytest.mark.asyncio
async def test_bot_traffic_reset_screen_shows_the_toman_shortfall(monkeypatch):
    traffic = _traffic_setup(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE)
        callback = _bot_callback('reset_traffic')
        await traffic.handle_reset_traffic(callback, await _loaded_user(db), db)

    text = _sent_text(callback)
    assert f'Не хватает: {SHORTFALL_LABEL}' in text


@pytest.mark.asyncio
async def test_bot_traffic_reset_refuses_then_debits_the_toman_price(monkeypatch):
    traffic = _traffic_setup(monkeypatch)
    prefill = _prefill(monkeypatch, traffic)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE)
        callback = _bot_callback('confirm_reset_traffic')
        await traffic.confirm_reset_traffic(callback, await _loaded_user(db), db)
        assert await _balance(db) == SHORT_BALANCE

    assert SHORTFALL_LABEL in _sent_text(callback)
    assert prefill == [SHORTFALL_TOMAN]

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        await traffic.confirm_reset_traffic(_bot_callback('confirm_reset_traffic'), await _loaded_user(db), db)

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]


# ---------------------------------------------------------------- bot admin: buy for a user


def _admin_setup(monkeypatch):
    import app.services.subscription_service as subscription_service_module
    from app.handlers.admin import users as admin_users

    async def profile(db, user_id):
        return {'user': await _loaded_user(db), 'subscription': await db.get(Subscription, 10)}

    monkeypatch.setattr(admin_users.UserService, 'get_user_profile', lambda self, db, user_id: profile(db, user_id))
    monkeypatch.setattr(admin_users, '_calculate_subscription_period_price', AsyncMock(return_value=PRICE_KOPEKS))
    monkeypatch.setattr(admin_users, 'SubscriptionService', lambda: _FakePanelSync(), raising=False)
    monkeypatch.setattr(subscription_service_module, 'SubscriptionService', lambda: _FakePanelSync())
    _tariff_purchase_price(monkeypatch)
    return admin_users


def _undecorated(module, name):
    """The handler without @admin_required / @error_handler (they need a real CallbackQuery)."""
    return inspect.unwrap(getattr(module, name))


ADMIN_FLOWS = {
    # The trailing field is the price carried in the callback data — Toman, like the column it came
    # from. A mismatch with the stored price makes the handler re-read the tariff and log a change.
    'subscription': (
        'admin_buy_subscription_confirm',
        'admin_buy_subscription_execute',
        f'a_b_c_d_1_30_{PRICE_KOPEKS}',
    ),
    'tariff': ('admin_buy_tariff_confirm', 'admin_buy_tariff_execute', f'a_b_c_d_1_2_30_{PRICE_KOPEKS}'),
}


@pytest.mark.parametrize('flow', sorted(ADMIN_FLOWS))
@pytest.mark.asyncio
async def test_admin_buy_for_user_uses_the_toman_price(monkeypatch, flow):
    import app.database.crud.user as user_crud

    admin_users = _admin_setup(monkeypatch)
    confirm, execute, data = ADMIN_FLOWS[flow]
    admin = SimpleNamespace(id=99, telegram_id=99, language='ru')

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=SHORT_BALANCE)
        shown = _bot_callback(data)
        await _undecorated(admin_users, confirm)(shown, admin, db)
        refused = _bot_callback(data)
        await _undecorated(admin_users, execute)(refused, admin, db)
        assert await _balance(db) == SHORT_BALANCE

    assert f'Не хватает: {SHORTFALL_LABEL}' in _sent_text(shown)
    assert 'Недостаточно средств' in refused.answer.await_args.args[0]

    debits = _spy_debits(monkeypatch, user_crud)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=RICH_BALANCE)
        await _undecorated(admin_users, execute)(_bot_callback(data), admin, db)

        assert debits == [PRICE_TOMAN]
        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert ('subscription_payment', PRICE_KOPEKS) in await _payments(db)


# ---------------------------------------------------------------- gift from balance (bot + cabinet /gift)


async def _seed_gift(db, *, balance_toman: int) -> None:
    from app.database.models import SystemSetting
    from app.services.gift_purchase_service import GIFT_ENABLED_KEY

    db.add(SystemSetting(key=GIFT_ENABLED_KEY, value='true'))
    db.add(User(id=1, telegram_id=1001, first_name='U', language='fa', status='active', balance_kopeks=balance_toman))
    db.add(
        Tariff(
            id=3,
            name='Gift',
            description='',
            is_active=True,
            show_in_gift=True,
            is_daily=False,
            period_prices={'30': PRICE_KOPEKS},
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


@pytest.mark.asyncio
async def test_gift_from_balance_refuses_with_the_toman_shortfall_then_debits_the_toman_price(monkeypatch):
    from app.services import gift_purchase_service as gifts

    monkeypatch.setattr(gifts, 'emit_transaction_side_effects', AsyncMock())

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_gift(db, balance_toman=SHORT_BALANCE)
        with pytest.raises(gifts.GiftInsufficientBalanceError) as caught:
            await gifts.purchase_gift_from_balance(
                db, 1, 3, 30, expected_price_kopeks=PRICE_KOPEKS, idempotency_key='gift-short'
            )
        assert await _balance(db) == SHORT_BALANCE

    # the bot shows and prefills this; the cabinet /gift page gates on the same Toman rule (frontend #13)
    assert caught.value.missing_toman == SHORTFALL_TOMAN

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_gift(db, balance_toman=RICH_BALANCE)
        result = await gifts.purchase_gift_from_balance(
            db, 1, 3, 30, expected_price_kopeks=PRICE_KOPEKS, idempotency_key='gift-rich'
        )

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('gift_payment', PRICE_KOPEKS)]

    assert result.remaining_balance_kopeks == RICH_BALANCE - PRICE_TOMAN


# ---------------------------------------------------------------- scheduled autopay renewal


async def _seed_autopay(db, *, balance_toman: int) -> None:
    await _seed(db, balance_toman=balance_toman)
    subscription = await db.get(Subscription, 10)
    now = datetime.now(UTC)
    subscription.autopay_enabled = True
    subscription.autopay_days_before = 3
    subscription.end_date = now + timedelta(days=1)
    subscription.updated_at = now - timedelta(days=1)  # not "recently updated by a webhook"
    await db.commit()


def _autopay_service(monkeypatch):
    import app.services.monitoring_service as monitoring
    from app.services.pricing_engine import RenewalPricing

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

    import app.services.pricing_engine as pricing_module

    pricing_module.pricing_engine.__dict__.pop('calculate_renewal_price', None)
    monkeypatch.setattr(PricingEngine, 'calculate_renewal_price', renewal_price)
    service = monitoring.MonitoringService(bot=None)
    service.subscription_service = _FakePanelSync()
    service._maybe_notify_autopay_failure = AsyncMock()
    monkeypatch.setattr(monitoring.notification_delivery_service, 'notify_autopay_success', AsyncMock())
    return monitoring, service


@pytest.mark.asyncio
async def test_autopay_skips_a_balance_below_the_toman_price(monkeypatch):
    _, service = _autopay_service(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_autopay(db, balance_toman=SHORT_BALANCE)
        await service._process_autopayments(db)

        assert await _balance(db) == SHORT_BALANCE
        assert await _payments(db) == []

    # the failure notice gets the catalog price (it is formatted with format_price)
    assert service._maybe_notify_autopay_failure.await_args.args[1] == PRICE_KOPEKS


@pytest.mark.asyncio
async def test_autopay_debits_the_toman_price(monkeypatch):
    _, service = _autopay_service(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_autopay(db, balance_toman=RICH_BALANCE)
        await service._process_autopayments(db)

        assert await _balance(db) == RICH_BALANCE - PRICE_TOMAN
        assert await _payments(db) == [('subscription_payment', PRICE_KOPEKS)]

    service._maybe_notify_autopay_failure.assert_not_awaited()


@pytest.mark.asyncio
async def test_autopay_refunds_the_toman_price_when_the_extension_fails(monkeypatch):
    monitoring, service = _autopay_service(monkeypatch)
    monkeypatch.setattr(monitoring, 'extend_subscription', AsyncMock(side_effect=RuntimeError('db down')))
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_autopay(db, balance_toman=RICH_BALANCE)
        await service._process_autopayments(db)

        assert await _balance(db) == RICH_BALANCE
        assert await _payments(db) == [('refund', PRICE_TOMAN)]
