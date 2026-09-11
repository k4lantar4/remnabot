"""Classic bot subscription screens for Persian users carry no Russian and no ₽ (F-009).

The classic (non-cabinet) subscription screens are reachable in cabinet mode only through old
messages or stray callbacks, but they still rendered hard-coded Russian: the tariff block of
``show_subscription_info`` («Тип: 🔄 Суточный», «Цена: 500.00 ₽/день», «До списания: …»), the
purchased-traffic list, the «(за N дн.)» labels of the add-on screens, the traffic switch keyboard
(«+500₽ (за 30 дн.)») and the classic renewal result.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings, settings
from app.handlers.subscription import common as subscription_common, purchase as subscription_purchase


CYRILLIC = re.compile('[А-Яа-яЁё]')
PERSIAN_DIGITS = re.compile('[۰-۹٠-٩]')
DAILY_PRICE_KOPEKS = 500_000  # catalog: 5,000 Toman a day


def _assert_persian(text: str) -> None:
    assert not CYRILLIC.search(text), text
    assert '₽' not in text, text
    assert not PERSIAN_DIGITS.search(text), text


def _callback() -> SimpleNamespace:
    message = MagicMock()
    message.edit_text = AsyncMock()
    return SimpleNamespace(message=message, answer=AsyncMock(), data='')


def _subscription(now: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        status='active',
        is_trial=False,
        start_date=now - timedelta(days=20),
        end_date=now + timedelta(days=10),
        traffic_used_gb=1.0,
        traffic_limit_gb=50,
        connected_squads=[],
        tariff_id=3,
        device_limit=2,
        last_daily_charge_at=now - timedelta(hours=2),
        is_daily_paused=False,
        remnawave_id=None,
    )


@pytest.fixture
def screen_env(monkeypatch):
    import app.database.crud.subscription as crud_subscription
    import app.database.crud.tariff as crud_tariff

    now = datetime.now(UTC)
    subscription = _subscription(now)
    tariff = SimpleNamespace(
        id=3,
        name='Daily',
        is_daily=True,
        traffic_limit_gb=50,
        device_limit=2,
        daily_price_kopeks=DAILY_PRICE_KOPEKS,
    )
    purchases = [
        SimpleNamespace(traffic_gb=10, created_at=now - timedelta(days=27), expires_at=now + timedelta(days=3))
    ]

    class _Service:
        async def sync_subscription_usage(self, db, sub):
            return None

        async def ensure_subscription_synced(self, db, sub):
            return True, None

    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    monkeypatch.setattr(Settings, 'is_tariffs_mode', lambda self: True)
    monkeypatch.setattr(Settings, 'is_devices_selection_enabled', lambda self: False)
    monkeypatch.setattr(Settings, 'should_hide_subscription_link', lambda self: True)
    monkeypatch.setattr(crud_subscription, 'check_and_update_subscription_status', AsyncMock(return_value=subscription))
    monkeypatch.setattr(crud_tariff, 'get_tariff_by_id', AsyncMock(return_value=tariff))
    monkeypatch.setattr(subscription_purchase, 'SubscriptionService', _Service)
    monkeypatch.setattr(subscription_purchase, 'get_servers_display_names', AsyncMock(return_value='🇩🇪 DE'))
    monkeypatch.setattr(subscription_purchase, 'get_display_subscription_link', lambda sub: None)
    monkeypatch.setattr(subscription_purchase, 'get_subscription_keyboard', lambda *args, **kwargs: None)

    result = MagicMock()
    result.scalars.return_value.all.return_value = purchases
    db = SimpleNamespace(refresh=AsyncMock(), execute=AsyncMock(return_value=result))
    user = SimpleNamespace(
        id=1,
        telegram_id=1001,
        language='fa',
        full_name='U',
        balance_kopeks=50_000,
        remnawave_id=None,
        subscription=subscription,
        promo_group=None,
        get_primary_promo_group=lambda: None,
    )
    return SimpleNamespace(db=db, user=user, subscription=subscription)


@pytest.mark.asyncio
async def test_daily_tariff_block_is_persian(screen_env):
    callback = _callback()

    await subscription_purchase.show_subscription_info(callback, screen_env.user, screen_env.db)

    text = callback.message.edit_text.call_args[0][0]
    block = text[text.index('<blockquote expandable>') :]
    _assert_persian(block)
    assert settings.format_price(DAILY_PRICE_KOPEKS) in block  # 5,000 تومان, the old /100 amount


@pytest.mark.asyncio
async def test_purchased_traffic_list_is_persian(screen_env):
    callback = _callback()

    await subscription_purchase.show_subscription_info(callback, screen_env.user, screen_env.db)

    text = callback.message.edit_text.call_args[0][0]
    purchased = text[text.rindex('<blockquote>') :]
    assert '10' in purchased
    assert not CYRILLIC.search(purchased), purchased


def test_traffic_switch_keyboard_is_persian(monkeypatch):
    monkeypatch.setattr(
        Settings,
        'get_traffic_packages',
        lambda self: [
            {'gb': 50, 'price': 1_000_000, 'enabled': True},
            {'gb': 100, 'price': 2_000_000, 'enabled': True},
            {'gb': 20, 'price': 500_000, 'enabled': True},
            {'gb': 0, 'price': 5_000_000, 'enabled': True},
        ],
    )
    monkeypatch.setattr(Settings, 'get_traffic_price', lambda self, gb: 1_000_000)

    keyboard = subscription_common.get_traffic_switch_keyboard(
        50,
        language='fa',
        subscription_end_date=datetime.now(UTC) + timedelta(days=15),
        discount_percent=10,
        base_traffic_gb=50,
    )
    confirm = subscription_common.get_confirm_switch_traffic_keyboard(100, 500_000, language='fa')

    labels = [button.text for row in keyboard.inline_keyboard + confirm.inline_keyboard for button in row]
    for label in labels:
        _assert_persian(label)
    assert any('15' in label for label in labels), labels  # «for 15 days» stays in the price label
