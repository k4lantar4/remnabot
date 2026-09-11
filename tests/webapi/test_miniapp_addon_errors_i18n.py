"""Miniapp device and traffic add-on texts follow the user's language (F-053, F-054).

A fa user changing the device count got Russian errors, buying extra traffic got English
errors, and both wrote Russian rows into the balance history. Machine ``code`` fields stay
unchanged; Russian output stays as it was.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
    balance: int = 500_000,
    device_price_kopeks: int | None = 1_000_000,
    traffic_topup_enabled: bool = True,
) -> list:
    now = datetime.now(UTC)
    return [
        User(
            id=1,
            telegram_id=1001,
            first_name='U',
            language=language,
            status='active',
            balance_kopeks=balance,
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
            device_price_kopeks=device_price_kopeks,
            traffic_topup_enabled=traffic_topup_enabled,
            traffic_topup_packages={'10': 3_000_000},
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
    from app.webapi.routes import miniapp

    monkeypatch.setattr(settings, 'RESET_TRAFFIC_ON_PAYMENT', False, raising=False)
    monkeypatch.setattr(settings, 'ADMIN_NOTIFICATIONS_ENABLED', False, raising=False)
    monkeypatch.setattr(settings, 'ALLOW_DEVICES_BELOW_TARIFF_LIMIT', False, raising=False)
    monkeypatch.setattr(settings, 'DEFAULT_DEVICE_LIMIT', 1, raising=False)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    monkeypatch.setattr(Settings, 'is_tariffs_mode', lambda self: True)
    monkeypatch.setattr(Settings, 'is_traffic_topup_blocked', lambda self: False)
    monkeypatch.setattr(miniapp, 'SubscriptionService', lambda: _FakePanelSync())
    monkeypatch.setattr(miniapp, 'with_admin_notification_service', AsyncMock(return_value=None))


@pytest.fixture
def charged_descriptions(monkeypatch):
    seen: list[str] = []
    original = user_crud.subtract_user_balance

    async def _spy(db, user, amount_kopeks, description, *args, **kwargs):
        seen.append(description)
        return await original(db, user, amount_kopeks, description, *args, **kwargs)

    monkeypatch.setattr(user_crud, 'subtract_user_balance', _spy)
    from app.webapi.routes import miniapp

    if hasattr(miniapp, 'subtract_user_balance'):
        monkeypatch.setattr(miniapp, 'subtract_user_balance', _spy)
    return seen


async def _seed_and_authorize(monkeypatch, db, language: str, **overrides) -> User:
    from app.webapi.routes import miniapp

    db.add_all(_rows(language, **overrides))
    await db.commit()
    loaded = await db.execute(select(User).options(selectinload(User.subscriptions)).where(User.id == 1))
    user = loaded.scalar_one()

    async def _fake_authorize(init_data, session):
        return user

    monkeypatch.setattr(miniapp, '_authorize_miniapp_user', _fake_authorize)
    return user


async def _payment_descriptions(db) -> list[str]:
    result = await db.execute(select(Transaction.description).where(Transaction.user_id == 1))
    return list(result.scalars().all())


# ---------------------------------------------------------------- devices


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'expected'),
    [
        ('fa', 'افزودن کاربر در دسترس نیست'),
        ('ru', 'Докупка устройств недоступна'),
    ],
)
async def test_devices_unavailable_in_user_language(monkeypatch, language, expected):
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppSubscriptionDevicesUpdateRequest

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_and_authorize(monkeypatch, db, language, device_price_kopeks=0)
        payload = MiniAppSubscriptionDevicesUpdateRequest.model_validate({'initData': 'stub', 'devices': 2})

        with pytest.raises(HTTPException) as caught:
            await miniapp.update_subscription_devices_endpoint(payload=payload, db=db)

    assert caught.value.detail == {'code': 'devices_unavailable', 'message': expected}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'expected'),
    [
        ('fa', 'از حداکثر تعداد کاربر (10) بیشتر است'),
        ('ru', 'Превышен максимальный лимит устройств (10)'),
    ],
)
async def test_devices_limit_exceeded_in_user_language(monkeypatch, language, expected):
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppSubscriptionDevicesUpdateRequest

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_and_authorize(monkeypatch, db, language)
        payload = MiniAppSubscriptionDevicesUpdateRequest.model_validate({'initData': 'stub', 'devices': 11})

        with pytest.raises(HTTPException) as caught:
            await miniapp.update_subscription_devices_endpoint(payload=payload, db=db)

    assert caught.value.detail['code'] == 'devices_limit_exceeded'
    assert caught.value.detail['message'] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'description', 'period_prefix', 'period_suffix'),
    [
        ('fa', 'تغییر تعداد کاربر از 1 به 2', 'تغییر تعداد کاربر از 1 به 2 برای ', ' روز'),
        ('ru', 'Изменение количества устройств с 1 до 2', 'Изменение количества устройств с 1 до 2 за ', ' дн.'),
    ],
)
async def test_devices_change_descriptions_in_user_language(
    monkeypatch, charged_descriptions, language, description, period_prefix, period_suffix
):
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppSubscriptionDevicesUpdateRequest

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_and_authorize(monkeypatch, db, language)
        payload = MiniAppSubscriptionDevicesUpdateRequest.model_validate({'initData': 'stub', 'devices': 2})

        await miniapp.update_subscription_devices_endpoint(payload=payload, db=db)

        (payment,) = await _payment_descriptions(db)

    assert charged_descriptions == [description]
    assert payment.startswith(period_prefix)
    assert payment.endswith(period_suffix)
    assert payment[len(period_prefix) : -len(period_suffix)].isdigit()


# ---------------------------------------------------------------- traffic


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'expected'),
    [
        ('fa', 'این سرویس امکان خرید ترافیک اضافه ندارد'),
        ('ru', 'Докупка трафика недоступна на вашем тарифе'),
    ],
)
async def test_traffic_topup_disabled_in_user_language(monkeypatch, language, expected):
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppTrafficTopupRequest

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_and_authorize(monkeypatch, db, language, traffic_topup_enabled=False)
        payload = MiniAppTrafficTopupRequest.model_validate({'initData': 'stub', 'gb': 10})

        with pytest.raises(HTTPException) as caught:
            await miniapp.purchase_traffic_topup_endpoint(payload=payload, db=db)

    assert caught.value.detail == {'code': 'traffic_topup_disabled', 'message': expected}


@pytest.mark.asyncio
async def test_traffic_topup_insufficient_balance_in_fa(monkeypatch):
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppTrafficTopupRequest

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_and_authorize(monkeypatch, db, 'fa', balance=100)
        payload = MiniAppTrafficTopupRequest.model_validate({'initData': 'stub', 'gb': 10})

        with pytest.raises(HTTPException) as caught:
            await miniapp.purchase_traffic_topup_endpoint(payload=payload, db=db)

    assert caught.value.detail['code'] == 'insufficient_balance'
    assert caught.value.detail['message'] == 'موجودی کافی نیست.'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'description', 'period_prefix', 'period_suffix'),
    [
        ('fa', 'تغییر بسته‌ی ترافیک از 100 گیگ به 200 گیگ', 'تغییر بسته‌ی ترافیک از 100 گیگ به 200 گیگ برای ', ' روز'),
        ('ru', 'Переключение трафика с 100GB на 200GB', 'Переключение трафика с 100GB на 200GB за ', ' дн.'),
    ],
)
async def test_traffic_switch_descriptions_in_user_language(
    monkeypatch, charged_descriptions, language, description, period_prefix, period_suffix
):
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppSubscriptionTrafficUpdateRequest

    monkeypatch.setattr(
        Settings,
        'get_traffic_packages',
        lambda self: [
            {'gb': 100, 'price': 1_000_000, 'enabled': True},
            {'gb': 200, 'price': 3_000_000, 'enabled': True},
        ],
    )
    monkeypatch.setattr(Settings, 'get_traffic_price', lambda self, gb: {100: 1_000_000, 200: 3_000_000}.get(gb, 0))

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_and_authorize(monkeypatch, db, language)
        payload = MiniAppSubscriptionTrafficUpdateRequest.model_validate({'initData': 'stub', 'traffic': 200})

        await miniapp.update_subscription_traffic_endpoint(payload=payload, db=db)

        (payment,) = await _payment_descriptions(db)

    assert charged_descriptions == [description]
    assert payment.startswith(period_prefix)
    assert payment.endswith(period_suffix)
    assert payment[len(period_prefix) : -len(period_suffix)].isdigit()
