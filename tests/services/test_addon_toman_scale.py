"""Add-on purchases (extra devices, extra traffic) take the Toman amount off the Toman balance.

Add-on prices (``device_price_kopeks``, traffic top-up packages, ``PRICE_PER_DEVICE``,
``TRAFFIC_*_PACKAGES_CONFIG``) used to be catalog prices — Toman x 100 — while
``User.balance_kopeks`` held raw Toman. The add-on paths compared the catalog number with the
balance and passed it straight to ``subtract_user_balance``, so a 10,000-Toman device needed (and
took) 1,000,000 Toman and the insufficient-funds shortfall mixed both scales. Same bug class as the
recurring daily charge (PR #21).

Revision ``0115`` put the price columns on the Toman scale, so the seed below is Toman and the
charge, the shortfall and the ledger row are all the same number.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import Settings, settings
from app.database.models import Base, Subscription, SubscriptionStatus, Tariff, Transaction, User
from tests.fixtures.sqlite_memory import memory_session


TABLES = list(Base.metadata.sorted_tables)
ROOT = Path(__file__).resolve().parents[2]

# Stored and charged are the same number since Phase C; both names are kept so the assertions
# still read as "the price column" and "the Toman charge".
DEVICE_PRICE_TOMAN = 10_000  # per device per month
DEVICE_PRICE_KOPEKS = DEVICE_PRICE_TOMAN
TRAFFIC_10GB_TOMAN = 30_000  # a 10 GB top-up
TRAFFIC_10GB_KOPEKS = TRAFFIC_10GB_TOMAN


class _FakePanelSync:
    async def update_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def create_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def enable_remnawave_user(self, *args, **kwargs):
        return True


def _rows(*, balance_toman: int) -> list:
    now = datetime.now(UTC)
    return [
        User(
            id=1,
            telegram_id=1001,
            first_name='U',
            language='fa',
            status='active',
            balance_kopeks=balance_toman,
            remnawave_id=9001,
        ),
        Tariff(
            id=1,
            name='monthly',
            description='',
            is_active=True,
            is_daily=False,
            period_prices={'30': 1_000_000},
            traffic_limit_gb=100,
            traffic_reset_mode='NO_RESET',
            device_limit=1,
            max_device_limit=10,
            device_price_kopeks=DEVICE_PRICE_KOPEKS,
            traffic_topup_enabled=True,
            traffic_topup_packages={'10': TRAFFIC_10GB_KOPEKS},
            max_topup_traffic_gb=0,
            allowed_squads=['squad-1'],
            display_order=1,
        ),
        Subscription(
            id=10,
            remnawave_short_id='add1',
            remnawave_id=9001,
            user_id=1,
            status=SubscriptionStatus.ACTIVE.value,
            is_trial=False,
            start_date=now - timedelta(days=1),
            # 30 charged days: device add-ons prorate by ceil(days left)
            end_date=now + timedelta(days=30) - timedelta(seconds=30),
            updated_at=now - timedelta(hours=1),
            traffic_limit_gb=100,
            traffic_used_gb=1.0,
            purchased_traffic_gb=0,
            device_limit=1,
            tariff_id=1,
            connected_squads=['squad-1'],
        ),
    ]


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """No Redis, panel, admin bot or multi-tariff branching in these tests."""
    import app.cabinet.routes.websocket as websocket_module
    import app.services.yandex_offline_conv_service as yandex_conv
    from app.services.user_cart_service import user_cart_service

    monkeypatch.setattr(settings, 'RESET_TRAFFIC_ON_PAYMENT', False, raising=False)
    monkeypatch.setattr(settings, 'ADMIN_NOTIFICATIONS_ENABLED', False, raising=False)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    monkeypatch.setattr(Settings, 'is_tariffs_mode', lambda self: True)
    monkeypatch.setattr(user_cart_service, 'save_user_cart', AsyncMock(return_value=True))
    monkeypatch.setattr(yandex_conv, 'store_cid_only', AsyncMock(return_value=None))
    monkeypatch.setattr(websocket_module, 'notify_user_devices_purchased', AsyncMock(), raising=False)
    monkeypatch.setattr(websocket_module, 'notify_user_traffic_purchased', AsyncMock(), raising=False)


async def _seed(db, *, balance_toman: int) -> User:
    db.add_all(_rows(balance_toman=balance_toman))
    await db.commit()
    return await db.get(User, 1)


async def _payments(db) -> list[int]:
    result = await db.execute(select(Transaction.amount_kopeks).where(Transaction.user_id == 1))
    return [abs(amount) for amount in result.scalars().all()]


async def _balance(db) -> int:
    result = await db.execute(select(User.balance_kopeks).where(User.id == 1))
    return result.scalar_one()


# ---------------------------------------------------------------- cabinet: devices


@pytest.mark.asyncio
async def test_cabinet_device_purchase_charges_the_toman_amount(monkeypatch):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices
    from app.cabinet.schemas.subscription import DevicePurchaseRequest

    monkeypatch.setattr(cabinet_devices, 'SubscriptionService', lambda: _FakePanelSync())
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=50_000)

        response = await cabinet_devices.purchase_devices(
            request=DevicePurchaseRequest(devices=1), subscription_id=None, user=user, db=db
        )

        assert await _balance(db) == 50_000 - DEVICE_PRICE_TOMAN
        assert await _payments(db) == [DEVICE_PRICE_KOPEKS]
        subscription = await db.get(Subscription, 10)

    assert subscription.device_limit == 2
    assert response['price_kopeks'] == DEVICE_PRICE_KOPEKS
    assert response['balance_kopeks'] == 50_000 - DEVICE_PRICE_TOMAN


@pytest.mark.asyncio
async def test_cabinet_device_purchase_reports_the_toman_shortfall(monkeypatch):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices
    from app.cabinet.schemas.subscription import DevicePurchaseRequest

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=4_000)

        with pytest.raises(HTTPException) as caught:
            await cabinet_devices.purchase_devices(
                request=DevicePurchaseRequest(devices=1), subscription_id=None, user=user, db=db
            )

        assert await _balance(db) == 4_000

    assert caught.value.status_code == 402
    assert caught.value.detail['missing_kopeks'] == DEVICE_PRICE_TOMAN - 4_000
    assert caught.value.detail['required_kopeks'] == DEVICE_PRICE_KOPEKS  # catalog, like PR #21


@pytest.mark.asyncio
async def test_cabinet_legacy_device_purchase_charges_the_toman_amount(monkeypatch):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices
    from app.cabinet.schemas.subscription import DevicePurchaseRequest

    monkeypatch.setattr(cabinet_devices, 'SubscriptionService', lambda: _FakePanelSync())
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=50_000)

        await cabinet_devices.purchase_devices_legacy(
            request=DevicePurchaseRequest(devices=1), subscription_id=None, user=user, db=db
        )

        assert await _balance(db) == 50_000 - DEVICE_PRICE_TOMAN
        assert await _payments(db) == [DEVICE_PRICE_KOPEKS]


# ---------------------------------------------------------------- cabinet: traffic


@pytest.mark.asyncio
async def test_cabinet_traffic_purchase_charges_the_toman_amount(monkeypatch):
    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic
    from app.cabinet.schemas.subscription import TrafficPurchaseRequest

    monkeypatch.setattr(cabinet_traffic, 'SubscriptionService', lambda: _FakePanelSync())
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=50_000)

        await cabinet_traffic.purchase_traffic(
            request=TrafficPurchaseRequest(gb=10), user=user, db=db, subscription_id=None
        )

        assert await _balance(db) == 50_000 - TRAFFIC_10GB_TOMAN
        assert await _payments(db) == [TRAFFIC_10GB_KOPEKS]


@pytest.mark.asyncio
async def test_cabinet_traffic_purchase_reports_the_toman_shortfall(monkeypatch):
    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic
    from app.cabinet.schemas.subscription import TrafficPurchaseRequest

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=10_000)

        with pytest.raises(HTTPException) as caught:
            await cabinet_traffic.purchase_traffic(
                request=TrafficPurchaseRequest(gb=10), user=user, db=db, subscription_id=None
            )

        assert await _balance(db) == 10_000

    assert caught.value.status_code == 402
    assert caught.value.detail['missing_amount'] == TRAFFIC_10GB_TOMAN - 10_000


@pytest.mark.asyncio
async def test_cabinet_traffic_switch_charges_the_toman_amount(monkeypatch):
    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic
    from app.cabinet.schemas.subscription import TrafficPurchaseRequest

    monkeypatch.setattr(
        Settings,
        'get_traffic_packages',
        lambda self: [
            {'gb': 100, 'price': 10_000, 'enabled': True},
            {'gb': 200, 'price': 30_000, 'enabled': True},
        ],
    )
    monkeypatch.setattr(cabinet_traffic, 'SubscriptionService', lambda: _FakePanelSync())
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=50_000)

        response = await cabinet_traffic.switch_traffic_package(
            request=TrafficPurchaseRequest(gb=200), user=user, db=db, subscription_id=None
        )

        # Switching charges the prorated difference, 30,000 - 10,000. Charged, recorded and
        # deducted are one number now; the old code put 2,000,000 in the ledger for the same switch.
        (charged,) = await _payments(db)
        assert charged == 20_000
        assert await _balance(db) == 50_000 - charged

    assert response['charged_kopeks'] == charged


# ---------------------------------------------------------------- Mini App


@pytest.mark.asyncio
async def test_miniapp_traffic_topup_charges_the_toman_amount(monkeypatch):
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppTrafficTopupRequest

    monkeypatch.setattr(miniapp, 'SubscriptionService', lambda: _FakePanelSync())
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, balance_toman=50_000)
        loaded = await db.execute(select(User).options(selectinload(User.subscriptions)).where(User.id == 1))
        user = loaded.scalar_one()

        async def _fake_authorize(init_data, session):
            return user

        monkeypatch.setattr(miniapp, '_authorize_miniapp_user', _fake_authorize)
        payload = MiniAppTrafficTopupRequest.model_validate({'initData': 'stub', 'gb': 10})
        await miniapp.purchase_traffic_topup_endpoint(payload=payload, db=db)

        # The 10 GB package is TRAFFIC_10GB_TOMAN; ledger row and deduction are the same number.
        (charged,) = await _payments(db)
        assert charged == TRAFFIC_10GB_TOMAN
        assert await _balance(db) == 50_000 - charged


# ---------------------------------------------------------------- saved cart after a top-up


@pytest.mark.asyncio
async def test_saved_device_cart_charges_the_toman_amount(monkeypatch):
    import app.services.subscription_auto_purchase_service as auto_module

    monkeypatch.setattr(auto_module, 'SubscriptionService', lambda: _FakePanelSync())
    monkeypatch.setattr(auto_module, '_delete_cart_for_subscription', AsyncMock())
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=50_000)
        cart = {'cart_mode': 'add_devices', 'devices_to_add': 1, 'price_kopeks': DEVICE_PRICE_KOPEKS}

        bought = await auto_module._auto_add_devices(db, user, cart, bot=None)

        assert bought is True
        assert await _balance(db) == 50_000 - DEVICE_PRICE_TOMAN
        assert await _payments(db) == [DEVICE_PRICE_KOPEKS]


@pytest.mark.asyncio
async def test_saved_traffic_cart_charges_the_toman_amount(monkeypatch):
    import app.services.subscription_auto_purchase_service as auto_module

    monkeypatch.setattr(auto_module, 'SubscriptionService', lambda: _FakePanelSync())
    monkeypatch.setattr(auto_module, '_delete_cart_for_subscription', AsyncMock())
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=50_000)
        cart = {
            'cart_mode': 'add_traffic',
            'subscription_id': 10,
            'traffic_gb': 10,
            'price_kopeks': TRAFFIC_10GB_KOPEKS,
        }

        bought = await auto_module._auto_add_traffic(db, user, cart, bot=None)

        assert bought is True
        assert await _balance(db) == 50_000 - TRAFFIC_10GB_TOMAN
        assert await _payments(db) == [TRAFFIC_10GB_KOPEKS]


@pytest.mark.asyncio
async def test_saved_device_cart_waits_when_the_toman_amount_is_not_covered(monkeypatch):
    import app.services.subscription_auto_purchase_service as auto_module

    monkeypatch.setattr(auto_module, '_delete_cart_for_subscription', AsyncMock())
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=4_000)
        cart = {'cart_mode': 'add_devices', 'devices_to_add': 1, 'price_kopeks': DEVICE_PRICE_KOPEKS}

        bought = await auto_module._auto_add_devices(db, user, cart, bot=None)

        assert bought is False
        assert await _balance(db) == 4_000


# ---------------------------------------------------------------- guard over every add-on site

# file -> functions that check or move the balance for a device / traffic add-on
ADDON_SITES = {
    'app/cabinet/routes/subscription_modules/devices.py': ('purchase_devices_legacy', 'purchase_devices'),
    'app/cabinet/routes/subscription_modules/traffic.py': ('purchase_traffic', 'switch_traffic_package'),
    'app/handlers/subscription/devices.py': (
        'confirm_change_devices',
        'execute_change_devices',
        'confirm_add_devices',
    ),
    'app/handlers/subscription/traffic.py': ('add_traffic', 'confirm_switch_traffic', 'execute_switch_traffic'),
    'app/webapi/routes/miniapp.py': (
        'update_subscription_traffic_endpoint',
        'update_subscription_devices_endpoint',
        'purchase_traffic_topup_endpoint',
    ),
    'app/services/subscription_auto_purchase_service.py': ('_auto_add_devices', '_auto_add_traffic'),
}
SITES = [(relative, name) for relative, names in ADDON_SITES.items() for name in names]
BALANCE_CALLS = {'subtract_user_balance', 'add_user_balance'}


def _function(relative: str, name: str) -> ast.AST:
    tree = ast.parse((ROOT / relative).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'{relative}: function {name} not found; update this guard')


def _call_name(call: ast.Call) -> str | None:
    return call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, 'id', None)


def _amount_argument(call: ast.Call) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == 'amount_kopeks':
            return keyword.value
    return call.args[2] if len(call.args) > 2 else None


@pytest.mark.parametrize(('relative', 'function_name'), SITES)
def test_addon_balance_moves_go_through_the_affordability_helper(relative, function_name):
    """Every add-on charge moves the balance, and none of them compares ``balance_kopeks`` inline.

    Before Phase C this guard also checked *which scale* each amount was on, because the add-on
    paths were the ones that kept passing a catalog price to ``subtract_user_balance``. Revision
    ``0115`` removed the second scale, so that half of the check has no meaning left and
    ``test_phase_c_single_scale.py`` now owns "nothing converts".

    What survives is the discipline that made the bug findable: affordability is decided by
    ``user_can_afford``, never by an inline comparison against the balance column.
    """
    func = _function(relative, function_name)
    where = f'{relative}:{function_name}'
    moved = False

    for node in ast.walk(func):
        if isinstance(node, ast.Call) and _call_name(node) in BALANCE_CALLS:
            moved = True
        if isinstance(node, ast.Compare):
            assert 'balance_kopeks' not in ast.unparse(node), (
                f'{where}:{node.lineno} compares the balance directly; use user_can_afford'
            )

    if function_name not in {'confirm_change_devices', 'confirm_switch_traffic'}:
        assert moved, f'{where}: no balance call found; guard is stale'
