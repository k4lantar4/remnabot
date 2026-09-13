"""What a user reads after an auto-purchase, add-on, daily event, gift or balance change (plan 2026-09-12
notifications, task 3, first PR: texts and buttons).

Audit 2026-09-12: these notices carried Russian f-strings (`📦 Тариф:`, manual top-up, gift, referral
commission, traffic reset, Stars activation) and bot-only keyboards (`menu_subscription` +
`back_to_menu`) that never pointed at the subscription the notice was about.
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings, settings
from app.localization.texts import get_texts


CABINET = 'https://panel.example.com'
CYRILLIC = re.compile('[Ѐ-ӿ]')
PERSIAN_DIGITS = re.compile('[۰-۹٠-٩]')
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _cabinet_multi_tariff(monkeypatch):
    monkeypatch.setattr(Settings, 'is_cabinet_mode', lambda self: True)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    monkeypatch.setattr(settings, 'MINIAPP_CUSTOM_URL', CABINET, raising=False)


def _urls(keyboard) -> list[str]:
    return [button.web_app.url for row in keyboard.inline_keyboard for button in row if button.web_app]


def _labels(keyboard) -> str:
    return ' '.join(button.text for row in keyboard.inline_keyboard for button in row)


def _assert_readable(text: str, keyboard=None) -> None:
    rendered = text + (_labels(keyboard) if keyboard else '')
    assert not CYRILLIC.search(rendered), rendered
    assert not PERSIAN_DIGITS.search(rendered), rendered


def _capture_delivery(monkeypatch, module) -> dict:
    captured: dict = {}

    async def send_notification(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(module.notification_delivery_service, 'send_notification', send_notification)
    return captured


def test_result_keyboard_opens_this_subscription_then_the_list():
    from app.utils.miniapp_buttons import build_subscription_result_keyboard

    keyboard = build_subscription_result_keyboard(get_texts('fa'), 42)

    _assert_readable('', keyboard)
    assert _urls(keyboard) == [f'{CABINET}/subscriptions/42', f'{CABINET}/subscriptions']


def test_result_keyboard_in_single_tariff_mode_keeps_the_main_menu(monkeypatch):
    from app.utils.miniapp_buttons import build_subscription_result_keyboard

    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)

    keyboard = build_subscription_result_keyboard(get_texts('fa'), 42)

    assert _urls(keyboard) == [f'{CABINET}/subscription']
    assert keyboard.inline_keyboard[-1][0].callback_data == 'back_to_menu'


def test_notice_datetime_is_jalali_for_fa():
    from app.utils.jalali_datetime import format_notice_datetime

    assert re.fullmatch(r'14\d\d/\d\d/\d\d \d\d:\d\d', format_notice_datetime(datetime(2026, 9, 13, tzinfo=UTC), 'fa'))


def test_auto_purchase_notices_use_keys_cabinet_buttons_and_user_dates():
    source = (ROOT / 'app/services/subscription_auto_purchase_service.py').read_text(encoding='utf-8')

    assert '📦 Тариф' not in source
    assert 'InlineKeyboardButton(' not in source
    assert 'format_local_datetime(new_end_date' not in source


def test_stars_activation_notice_has_no_russian_tariff_suffix():
    source = (ROOT / 'app/services/payment/stars.py').read_text(encoding='utf-8')

    assert '📦 Тариф' not in source
    assert "text='📱 Моя подписка'" not in source


async def test_daily_traffic_reset_notice_is_localized(monkeypatch):
    from app.services import daily_subscription_service as module

    captured = _capture_delivery(monkeypatch, module)
    service = module.DailySubscriptionService.__new__(module.DailySubscriptionService)
    service._bot = None
    user = SimpleNamespace(id=7, telegram_id=7007, language='fa')
    subscription = SimpleNamespace(id=42, tariff=SimpleNamespace(name='Pro'), traffic_limit_gb=50)

    await service._notify_traffic_reset(user, subscription, 10)

    text = captured['telegram_message']
    _assert_readable(text)
    assert 'Pro' in text and '10' in text and '50' in text


async def test_daily_insufficient_balance_opens_topup_and_this_subscription(monkeypatch):
    from app.services import daily_subscription_service as module

    captured = _capture_delivery(monkeypatch, module)
    service = module.DailySubscriptionService.__new__(module.DailySubscriptionService)
    service._bot = None
    user = SimpleNamespace(id=7, telegram_id=7007, language='fa', balance_kopeks=500)
    subscription = SimpleNamespace(id=42, tariff=SimpleNamespace(name='Pro'))

    await service._notify_insufficient_balance(user, subscription, 5_000)

    keyboard = captured['telegram_markup']
    _assert_readable(captured['telegram_message'], keyboard)
    assert _urls(keyboard) == [f'{CABINET}/balance/top-up', f'{CABINET}/subscriptions/42']


async def test_manual_topup_notice_is_localized(monkeypatch):
    import app.services.manual_topup_service as manual_topup
    from app.services.payment.common import PaymentCommonMixin

    monkeypatch.setattr(Settings, 'is_notifications_enabled', lambda self: True)
    monkeypatch.setattr(PaymentCommonMixin, 'build_topup_success_keyboard', AsyncMock(return_value=None))
    monkeypatch.setattr('app.services.payment.common.notify_email_user_topup', AsyncMock())
    bot = SimpleNamespace(send_message=AsyncMock())
    user = SimpleNamespace(id=7, telegram_id=7007, language='fa', balance_kopeks=150_000)

    await manual_topup._notify_user(user, 50_000, SimpleNamespace(id=701), bot=bot)

    text = bot.send_message.await_args.args[1]
    _assert_readable(text)
    assert settings.format_balance(50_000) in text
    assert settings.format_balance(150_000) in text
    assert '701' in text


async def test_admin_balance_credit_renews_the_only_subscription(monkeypatch):
    from app.services import user_service as module

    captured = _capture_delivery(monkeypatch, module)
    user = SimpleNamespace(
        id=7,
        telegram_id=7007,
        language='fa',
        balance_kopeks=150_000,
        subscriptions=[SimpleNamespace(id=42, status='active')],
    )

    await module.UserService.__new__(module.UserService)._send_balance_notification(None, user, 50_000, 'admin')

    keyboard = captured['telegram_markup']
    _assert_readable('', keyboard)
    assert _urls(keyboard) == [f'{CABINET}/subscriptions/42/renew']


async def test_admin_balance_credit_with_several_subscriptions_opens_the_list(monkeypatch):
    from app.services import user_service as module

    captured = _capture_delivery(monkeypatch, module)
    user = SimpleNamespace(
        id=7,
        telegram_id=7007,
        language='fa',
        balance_kopeks=150_000,
        subscriptions=[SimpleNamespace(id=42, status='active'), SimpleNamespace(id=43, status='expired')],
    )

    await module.UserService.__new__(module.UserService)._send_balance_notification(None, user, 50_000, 'admin')

    assert _urls(captured['telegram_markup']) == [f'{CABINET}/subscriptions']


async def test_gift_notice_is_localized_and_keeps_the_activation_callback(monkeypatch):
    from app import bot_factory
    from app.services import guest_purchase_service as module

    bot = SimpleNamespace(send_message=AsyncMock())

    @asynccontextmanager
    async def fake_create_bot(*args, **kwargs):
        yield bot

    monkeypatch.setattr(bot_factory, 'create_bot', fake_create_bot)
    monkeypatch.setattr(settings, 'BOT_TOKEN', 'token', raising=False)
    purchase = SimpleNamespace(
        id=5,
        user=SimpleNamespace(telegram_id=7007, language='fa'),
        contact_value='Sara',
        gift_message='enjoy',
        period_days=30,
    )

    await module._send_telegram_gift_notification(purchase, is_pending_activation=True, tariff_name='Pro')

    kwargs = bot.send_message.await_args.kwargs
    _assert_readable(kwargs['text'], kwargs['reply_markup'])
    assert 'Pro' in kwargs['text'] and '30' in kwargs['text'] and 'Sara' in kwargs['text']
    # The cabinet has no page that activates a gift by id, so the button stays a bot callback.
    assert kwargs['reply_markup'].inline_keyboard[0][0].callback_data == 'gift_activate:5'


def test_referral_commission_and_promocode_balance_lines_are_keyed():
    referral = (ROOT / 'app/services/referral_service.py').read_text(encoding='utf-8')
    promocode = (ROOT / 'app/services/promocode_service.py').read_text(encoding='utf-8')

    assert 'Комиссия с покупки!' not in referral
    assert "'REFERRAL_PURCHASE_COMMISSION_NOTICE'" in referral
    assert '₽' not in promocode.split("'PROMOCODE_BALANCE_BONUS_LINE'")[0].rsplit('balance_bonus_kopeks > 0', 1)[-1]
    assert "'PROMOCODE_BALANCE_BONUS_LINE'" in promocode
