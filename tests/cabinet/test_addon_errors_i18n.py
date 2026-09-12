"""Device and traffic add-on texts follow the user's language (F-053, F-054).

The cabinet answered a fa user's extra-device purchase with Russian errors and a Russian
success message, the extra-traffic endpoints refused in English, and both wrote Russian or
English rows into the balance history. Russian output stays as it was.

The device-price and reduction-info refusals also carry upstream's machine ``reason_code``
(04fa5163), which the cabinet already maps to its own locale.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

import app.database.crud.user as user_crud
from app.config import Settings, settings
from app.database.models import Base, Subscription, SubscriptionStatus, Tariff, Transaction, User
from tests.fixtures.sqlite_memory import memory_session


TABLES = list(Base.metadata.sorted_tables)


class _FakePanelSync:
    async def update_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def create_remnawave_user(self, db, subscription, **kwargs):
        return SimpleNamespace(id=9001, used_traffic_bytes=0)


def _rows(
    language: str,
    *,
    device_price_kopeks: int | None = 10_000,
    max_device_limit: int | None = 10,
    device_limit: int = 1,
    traffic_topup_enabled: bool = True,
    max_topup_traffic_gb: int = 0,
    restricted: bool = False,
) -> list:
    now = datetime.now(UTC)
    return [
        User(
            id=1,
            telegram_id=1001,
            first_name='U',
            language=language,
            status='active',
            balance_kopeks=500_000,
            remnawave_id=9001,
            restriction_subscription=restricted,
        ),
        Tariff(
            id=1,
            name='monthly',
            description='',
            is_active=True,
            is_daily=False,
            period_prices={'30': 10_000},
            traffic_limit_gb=100,
            traffic_reset_mode='NO_RESET',
            device_limit=1,
            max_device_limit=max_device_limit,
            device_price_kopeks=device_price_kopeks,
            traffic_topup_enabled=traffic_topup_enabled,
            traffic_topup_packages={'10': 30_000},
            max_topup_traffic_gb=max_topup_traffic_gb,
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
            end_date=now + timedelta(days=30) - timedelta(seconds=30),
            updated_at=now - timedelta(hours=1),
            traffic_limit_gb=100,
            traffic_used_gb=1.0,
            purchased_traffic_gb=0,
            device_limit=device_limit,
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
    monkeypatch.setattr(settings, 'ALLOW_DEVICES_BELOW_TARIFF_LIMIT', False, raising=False)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    monkeypatch.setattr(Settings, 'is_tariffs_mode', lambda self: True)
    monkeypatch.setattr(user_cart_service, 'save_user_cart', AsyncMock(return_value=True))
    monkeypatch.setattr(yandex_conv, 'store_cid_only', AsyncMock(return_value=None))
    monkeypatch.setattr(websocket_module, 'notify_user_devices_purchased', AsyncMock(), raising=False)
    monkeypatch.setattr(websocket_module, 'notify_user_traffic_purchased', AsyncMock(), raising=False)


@pytest.fixture
def charged_descriptions(monkeypatch):
    """Record what subtract_user_balance writes into the balance history."""
    seen: list[str] = []
    original = user_crud.subtract_user_balance

    async def _spy(db, user, amount_kopeks, description, *args, **kwargs):
        seen.append(description)
        return await original(db, user, amount_kopeks, description, *args, **kwargs)

    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic

    # devices.py imports it inside the handler, traffic.py at module level
    monkeypatch.setattr(user_crud, 'subtract_user_balance', _spy)
    monkeypatch.setattr(cabinet_traffic, 'subtract_user_balance', _spy)
    return seen


async def _seed(db, language: str, **overrides) -> User:
    db.add_all(_rows(language, **overrides))
    await db.commit()
    return await db.get(User, 1)


async def _payment_descriptions(db) -> list[str]:
    result = await db.execute(select(Transaction.description).where(Transaction.user_id == 1))
    return list(result.scalars().all())


# ---------------------------------------------------------------- devices


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'message', 'description'),
    [
        ('fa', '1 کاربر اضافه شد', 'خرید 1 کاربر اضافه'),
        ('ru', 'Добавлено 1 устройств', 'Покупка 1 доп. устройств'),
    ],
)
async def test_device_purchase_texts_in_user_language(
    monkeypatch, charged_descriptions, language, message, description
):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices
    from app.cabinet.schemas.subscription import DevicePurchaseRequest

    monkeypatch.setattr(cabinet_devices, 'SubscriptionService', lambda: _FakePanelSync())
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, language)

        response = await cabinet_devices.purchase_devices(
            request=DevicePurchaseRequest(devices=1), subscription_id=None, user=user, db=db
        )

        assert await _payment_descriptions(db) == [description]

    assert response['message'] == message
    assert charged_descriptions == [description]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'expected'),
    [
        ('fa', 'افزودن کاربر در دسترس نیست'),
        ('ru', 'Докупка устройств недоступна'),
    ],
)
async def test_device_purchase_unavailable_in_user_language(monkeypatch, language, expected):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices
    from app.cabinet.schemas.subscription import DevicePurchaseRequest

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, language, device_price_kopeks=0)

        for handler in (cabinet_devices.purchase_devices, cabinet_devices.purchase_devices_legacy):
            with pytest.raises(HTTPException) as caught:
                await handler(request=DevicePurchaseRequest(devices=1), subscription_id=None, user=user, db=db)
            assert caught.value.detail == expected

        with pytest.raises(HTTPException) as caught:
            await cabinet_devices.save_devices_cart(
                request=DevicePurchaseRequest(devices=1), subscription_id=None, user=user, db=db
            )
        assert caught.value.detail == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'expected'),
    [
        ('fa', 'حداکثر تعداد کاربر: 3'),
        ('ru', 'Максимальное количество устройств: 3'),
    ],
)
async def test_device_purchase_max_limit_in_user_language(monkeypatch, language, expected):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices
    from app.cabinet.schemas.subscription import DevicePurchaseRequest

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, language, max_device_limit=3, device_limit=3)

        with pytest.raises(HTTPException) as caught:
            await cabinet_devices.purchase_devices(
                request=DevicePurchaseRequest(devices=1), subscription_id=None, user=user, db=db
            )

    assert caught.value.detail == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'expected'),
    [
        ('fa', 'تعداد کاربر به حداکثر رسیده است (3)'),
        ('ru', 'Достигнут максимум устройств (3)'),
    ],
)
async def test_device_price_reason_in_user_language_with_code(monkeypatch, language, expected):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, language, max_device_limit=3, device_limit=3)
        info = await cabinet_devices.get_device_price(devices=1, subscription_id=None, user=user, db=db)

    assert info['available'] is False
    assert info['reason'] == expected
    assert info['reason_code'] == 'max_devices_reached'


@pytest.mark.asyncio
async def test_device_price_unavailable_reason_code(monkeypatch):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, 'fa', device_price_kopeks=0)
        info = await cabinet_devices.get_device_price(devices=1, subscription_id=None, user=user, db=db)

    assert info['reason'] == 'افزودن کاربر در دسترس نیست'
    assert info['reason_code'] == 'devices_unavailable'


@pytest.mark.asyncio
async def test_device_price_can_add_limited_reason_code(monkeypatch):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, 'fa', max_device_limit=3, device_limit=2)
        info = await cabinet_devices.get_device_price(devices=5, subscription_id=None, user=user, db=db)

    assert info['reason'] == 'حداکثر 1 کاربر دیگر می‌شود اضافه کرد'
    assert info['reason_code'] == 'can_add_limited'


@pytest.mark.asyncio
async def test_reduction_info_carries_reason_code(monkeypatch):
    import app.cabinet.routes.subscription_modules.devices as cabinet_devices

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, 'fa')
        info = await cabinet_devices.get_device_reduction_info(subscription_id=None, user=user, db=db)

    assert info['available'] is False
    assert info['reason_code'] == 'at_minimum'


# ---------------------------------------------------------------- traffic


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'expected'),
    [
        ('fa', 'این سرویس امکان خرید ترافیک اضافه ندارد'),
        ('ru', 'Докупка трафика недоступна на вашем тарифе'),
        ('en', "Your tariff doesn't allow extra traffic"),
    ],
)
async def test_traffic_purchase_tariff_disabled_in_user_language(monkeypatch, language, expected):
    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic
    from app.cabinet.schemas.subscription import TrafficPurchaseRequest

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, language, traffic_topup_enabled=False)

        with pytest.raises(HTTPException) as caught:
            await cabinet_traffic.purchase_traffic(
                request=TrafficPurchaseRequest(gb=10), user=user, db=db, subscription_id=None
            )

    assert caught.value.detail == expected


@pytest.mark.asyncio
async def test_traffic_purchase_limit_exceeded_in_fa(monkeypatch):
    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic
    from app.cabinet.schemas.subscription import TrafficPurchaseRequest

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, 'fa', max_topup_traffic_gb=105)

        with pytest.raises(HTTPException) as caught:
            await cabinet_traffic.purchase_traffic(
                request=TrafficPurchaseRequest(gb=10), user=user, db=db, subscription_id=None
            )

    assert caught.value.detail == 'از سقف ترافیک بیشتر می‌شود. سقف: 105 گیگ، قابل خرید: 5 گیگ'


@pytest.mark.asyncio
async def test_traffic_purchase_restricted_in_fa(monkeypatch):
    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic
    from app.cabinet.schemas.subscription import TrafficPurchaseRequest

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, 'fa', restricted=True)

        with pytest.raises(HTTPException) as caught:
            await cabinet_traffic.purchase_traffic(
                request=TrafficPurchaseRequest(gb=10), user=user, db=db, subscription_id=None
            )

    assert caught.value.detail == 'خرید اشتراک برای این حساب محدود شده است'


def _two_traffic_packages(monkeypatch):
    monkeypatch.setattr(
        Settings,
        'get_traffic_packages',
        lambda self: [
            {'gb': 100, 'price': 10_000, 'enabled': True},
            {'gb': 200, 'price': 30_000, 'enabled': True},
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'description'),
    [
        ('fa', 'تغییر بسته‌ی ترافیک از 100 گیگ به 200 گیگ'),
        ('ru', 'Переключение трафика с 100GB на 200GB'),
        ('en', 'Traffic upgrade from 100GB to 200GB'),
    ],
)
async def test_traffic_switch_description_in_user_language(monkeypatch, charged_descriptions, language, description):
    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic
    from app.cabinet.schemas.subscription import TrafficPurchaseRequest

    _two_traffic_packages(monkeypatch)
    monkeypatch.setattr(cabinet_traffic, 'SubscriptionService', lambda: _FakePanelSync())
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, language)

        await cabinet_traffic.switch_traffic_package(
            request=TrafficPurchaseRequest(gb=200), user=user, db=db, subscription_id=None
        )

        assert await _payment_descriptions(db) == [description]

    assert charged_descriptions == [description]


@pytest.mark.asyncio
async def test_traffic_switch_same_package_in_fa(monkeypatch):
    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic
    from app.cabinet.schemas.subscription import TrafficPurchaseRequest

    _two_traffic_packages(monkeypatch)
    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, 'fa')

        with pytest.raises(HTTPException) as caught:
            await cabinet_traffic.switch_traffic_package(
                request=TrafficPurchaseRequest(gb=100), user=user, db=db, subscription_id=None
            )

    assert caught.value.detail == 'همین بسته‌ی ترافیک فعال است'
