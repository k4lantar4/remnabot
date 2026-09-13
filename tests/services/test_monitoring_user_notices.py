"""What a user reads in scheduled monitoring notices (plan 2026-09-12 notifications, task 1).

Audit 2026-09-12: the expired, trial-ending, winback, autopay and legacy-autopay notices were hardcoded
Russian with Russian buttons, `menu_support` stayed a bot callback in cabinet mode, the traffic warning
had no button and no tariff name, and the trial window ignored `TRIAL_WARNING_HOURS`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings, settings
from app.database.models import (
    PromoGroup,
    SentNotification,
    Subscription,
    SubscriptionStatus,
    Tariff,
    User,
    UserPromoGroup,
    UserStatus,
)
from app.localization.texts import get_texts
from app.services.monitoring_service import MonitoringService
from app.services.notification_settings_service import NotificationSettingsService
from tests.fixtures.sqlite_memory import memory_session


CABINET = 'https://panel.example.com'
CYRILLIC = re.compile('[Ѐ-ӿ]')
PERSIAN_DIGITS = re.compile('[۰-۹٠-٩]')


@pytest.fixture(autouse=True)
def _cabinet_multi_tariff(monkeypatch):
    monkeypatch.setattr(Settings, 'is_cabinet_mode', lambda self: True)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    monkeypatch.setattr(settings, 'MINIAPP_CUSTOM_URL', CABINET, raising=False)


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=7, telegram_id=7007, language='fa', balance_kopeks=50_000, status='active')


def _subscription(sub_id: int = 42) -> SimpleNamespace:
    return SimpleNamespace(
        id=sub_id,
        user_id=7,
        end_date=datetime.now(UTC) + timedelta(hours=1),
        tariff=SimpleNamespace(name='Pro'),
        autopay_enabled=False,
    )


def _urls(keyboard) -> list[str]:
    return [button.web_app.url for row in keyboard.inline_keyboard for button in row if button.web_app]


def _labels(keyboard) -> str:
    return ' '.join(button.text for row in keyboard.inline_keyboard for button in row)


def _assert_readable(text: str, keyboard=None) -> None:
    rendered = text + (_labels(keyboard) if keyboard else '')
    assert not CYRILLIC.search(rendered), rendered
    assert not PERSIAN_DIGITS.search(rendered), rendered


def test_expired_notice_names_the_tariff_and_opens_its_renewal():
    text, keyboard = MonitoringService._build_expired_notice(get_texts('fa'), _subscription())

    _assert_readable(text, keyboard)
    assert 'Pro' in text
    assert f'{CABINET}/subscriptions/42/renew' in _urls(keyboard)
    assert f'{CABINET}/balance/top-up' in _urls(keyboard)


def test_trial_ending_notice_quotes_the_configured_window():
    text, keyboard = MonitoringService._build_trial_ending_notice(get_texts('fa'), _subscription(), 5)

    _assert_readable(text, keyboard)
    assert '5' in text
    assert 'Pro' in text
    assert f'{CABINET}/balance/top-up' in _urls(keyboard)


def test_followup_keyboard_opens_cabinet_support_and_the_discount_button_is_localized():
    keyboard = MonitoringService._build_followup_keyboard(get_texts('fa'), _subscription(), offer_id=9)

    _assert_readable('', keyboard)
    urls = _urls(keyboard)
    assert f'{CABINET}/support' in urls
    assert f'{CABINET}/subscriptions/42/renew' in urls
    assert any(button.callback_data == 'claim_discount_9' for row in keyboard.inline_keyboard for button in row)


@pytest.mark.parametrize('is_final', [False, True])
def test_autopay_failed_notice_names_the_tariff_and_opens_its_renewal(is_final):
    text, keyboard = MonitoringService._build_autopay_failed_notice(
        get_texts('fa'), _subscription(), balance=50_000, required=60_000, is_final=is_final
    )

    _assert_readable(text, keyboard)
    assert 'Pro' in text
    assert f'{CABINET}/balance/top-up' in _urls(keyboard)
    assert f'{CABINET}/subscriptions/42/renew' in _urls(keyboard)


def test_autopay_success_tariff_line_is_localized():
    line = MonitoringService._tariff_line(get_texts('fa'), _subscription())

    _assert_readable(line)
    assert 'Pro' in line


def test_legacy_autopay_notice_is_localized_with_a_renew_button():
    text, keyboard = MonitoringService._build_legacy_autopay_notice(get_texts('fa'), _subscription())

    _assert_readable(text, keyboard)
    assert f'{CABINET}/subscriptions/42/renew' in _urls(keyboard)


@pytest.mark.parametrize('reason', ['final', 'charge_error', 'insufficient'])
def test_autopay_failure_email_reasons_are_localized(reason):
    _assert_readable(MonitoringService._autopay_failure_reason(get_texts('fa'), reason))


def test_traffic_warning_names_the_tariff_and_opens_the_subscription():
    text, keyboard = MonitoringService._build_traffic_warning(get_texts('fa'), _subscription(), 9.5, 10, 95.0)

    _assert_readable(text, keyboard)
    assert 'Pro' in text
    assert f'{CABINET}/subscriptions/42' in _urls(keyboard)


async def test_expiring_notice_subscriptions_button_is_localized_and_opens_the_list(monkeypatch):
    service = MonitoringService.__new__(MonitoringService)
    service._send_message_with_logo = AsyncMock()
    user = _user()

    assert await service._send_subscription_expiring_notification(user, _subscription(), 3)

    call = service._send_message_with_logo.await_args
    assert call.kwargs['user'] is user
    _assert_readable('', call.kwargs['reply_markup'])
    assert f'{CABINET}/subscriptions' in _urls(call.kwargs['reply_markup'])


async def test_expired_notice_skips_blocked_users():
    service = MonitoringService.__new__(MonitoringService)
    service._send_message_with_logo = AsyncMock()
    user = _user()

    await service._send_subscription_expired_notification(user, _subscription())

    assert service._send_message_with_logo.await_args.kwargs['user'] is user


async def test_trial_window_follows_the_setting(monkeypatch):
    monkeypatch.setattr(
        NotificationSettingsService, 'are_notifications_globally_enabled', classmethod(lambda cls: True)
    )
    monkeypatch.setattr(Settings, 'get_trial_warning_hours', lambda self: 5)
    tables = (
        User.__table__,
        Subscription.__table__,
        Tariff.__table__,
        PromoGroup.__table__,
        UserPromoGroup.__table__,
        SentNotification.__table__,
    )
    async with memory_session(monkeypatch, tables) as db:
        user = User(telegram_id=1, username='u1', first_name='U', status=UserStatus.ACTIVE.value, language='fa')
        db.add(user)
        await db.commit()
        now = datetime.now(UTC)
        db.add(
            Subscription(
                user_id=user.id,
                status=SubscriptionStatus.ACTIVE.value,
                is_trial=True,
                start_date=now - timedelta(days=2),
                end_date=now + timedelta(hours=4),
                remnawave_short_id='trial1',
            )
        )
        await db.commit()
        service = MonitoringService.__new__(MonitoringService)
        service.bot = SimpleNamespace(send_message=AsyncMock())
        service._log_monitoring_event = AsyncMock()
        service._send_trial_ending_notification = AsyncMock(return_value=True)

        await service._check_trial_expiring_soon(db)

        service._send_trial_ending_notification.assert_awaited_once()
        assert service._send_trial_ending_notification.await_args.args[2] == 5
