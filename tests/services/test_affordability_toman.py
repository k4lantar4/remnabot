"""Balance checks, shortfalls and debits compare the Toman balance with the Toman price.

``User.balance_kopeks`` is raw Toman since Phase B; tariff prices, switch costs, server and traffic
prices and the trial activation price are catalog ``price_kopeks`` (Toman x 100). These paths
compared the two directly, reported ``price - balance`` as the shortfall and debited the catalog
number: a 200,000-Toman tariff switch needed (and took) 20,000,000 Toman.

Fixed per site as check + debit + refund together (the PR #27 / #32 pattern): affordability via
``user_can_afford``, shortfall via ``missing_toman`` (Toman), debit and refund via
``catalog_price_in_toman``. Transaction rows stay on the catalog scale (``subscription_payment``).

Every surface is pinned with the same numbers: a 150,000-Toman balance against a 200,000-Toman
price (catalog 20,000,000) is refused with a 50,000-Toman shortfall; a 250,000-Toman balance gets
exactly 200,000 debited.
"""

from __future__ import annotations

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

PRICE_KOPEKS = 20_000_000  # catalog
PRICE_TOMAN = 200_000
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

    pricing_module.pricing_engine.__dict__.pop('calculate_tariff_switch_cost', None)
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
    assert response['upgrade_cost_kopeks'] == PRICE_KOPEKS


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
