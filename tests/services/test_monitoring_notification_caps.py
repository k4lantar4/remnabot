"""Tests for monitoring notification caps (Task 24)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services.monitoring_notify_limiter import MonitoringNotifyLimiter
from app.services.monitoring_service import MonitoringService


def _make_user(user_id: int = 1, telegram_id: int = 1001) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        telegram_id=telegram_id,
        language='fa',
        status='active',
        balance_kopeks=0,
    )


def _make_subscription(
    sub_id: int,
    user: SimpleNamespace,
    *,
    end_date: datetime | None = None,
    traffic_limit_gb: int = 10,
    traffic_used_gb: float = 9.0,
    status: str = 'active',
) -> SimpleNamespace:
    return SimpleNamespace(
        id=sub_id,
        user_id=user.id,
        user=user,
        end_date=end_date,
        traffic_limit_gb=traffic_limit_gb,
        traffic_used_gb=traffic_used_gb,
        status=status,
        is_trial=False,
        tariff=None,
        autopay_enabled=False,
    )


@pytest.fixture(autouse=True)
def _cap_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'MONITORING_NOTIFY_MAX_PER_USER_DAY', 5, raising=False)
    monkeypatch.setattr(settings, 'TRAFFIC_WARNING_MAX_PER_SUB', 3, raising=False)
    monkeypatch.setattr(settings, 'MONITORING_EXPIRED_LOOKBACK_DAYS', 30, raising=False)


@pytest.mark.asyncio
async def test_followups_cap_many_expired_subscriptions_for_one_user():
    user = _make_user()
    now = datetime.now(UTC)
    subscriptions = [
        _make_subscription(
            sub_id=i,
            user=user,
            end_date=now - timedelta(days=1, hours=i),
        )
        for i in range(100)
    ]

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=subscriptions))))
    )

    service = MonitoringService(bot=AsyncMock())
    service._notify_limiter = MonitoringNotifyLimiter()
    service._send_expired_day1_notification = AsyncMock(return_value=True)
    service._log_monitoring_event = AsyncMock()

    with (
        patch(
            'app.services.monitoring_service.NotificationSettingsService.are_notifications_globally_enabled',
            return_value=True,
        ),
        patch(
            'app.services.monitoring_service.NotificationSettingsService.is_expired_1d_enabled',
            return_value=True,
        ),
        patch(
            'app.services.monitoring_service.NotificationSettingsService.is_second_wave_enabled',
            return_value=False,
        ),
        patch(
            'app.services.monitoring_service.NotificationSettingsService.is_third_wave_enabled',
            return_value=False,
        ),
        patch('app.services.monitoring_service.notification_sent', AsyncMock(return_value=False)),
        patch('app.services.monitoring_service.record_notification', AsyncMock()) as record_mock,
    ):
        await service._check_expired_subscription_followups(db)

    assert service._send_expired_day1_notification.await_count == 5
    assert record_mock.await_count == 5


@pytest.mark.asyncio
async def test_traffic_warning_blocked_after_lifetime_cap():
    user = _make_user()
    subscription = _make_subscription(1, user, traffic_used_gb=9.5)

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[subscription]))))
    )

    service = MonitoringService(bot=AsyncMock())
    service._notify_limiter = MonitoringNotifyLimiter()
    service.bot.send_message = AsyncMock()

    with (
        patch(
            'app.utils.notification_prefs.is_traffic_warning_enabled',
            return_value=True,
        ),
        patch(
            'app.utils.notification_prefs.get_traffic_warning_percent',
            return_value=80,
        ),
        patch('app.services.monitoring_service.count_notifications', AsyncMock(return_value=3)),
        patch('app.services.monitoring_service.cache.get', AsyncMock(return_value=None)),
        patch('app.services.monitoring_service.record_notification', AsyncMock()) as record_mock,
    ):
        await service._check_traffic_warnings(db)

    service.bot.send_message.assert_not_awaited()
    record_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_instant_skips_when_already_recorded():
    user = _make_user()
    subscription = _make_subscription(1, user, end_date=datetime.now(UTC) - timedelta(hours=1))

    db = AsyncMock()

    service = MonitoringService(bot=AsyncMock())
    service._send_subscription_expired_notification = AsyncMock(return_value=True)

    with (
        patch(
            'app.services.monitoring_service.get_expired_subscriptions',
            AsyncMock(return_value=[subscription]),
        ),
        patch(
            'app.database.crud.subscription.is_recently_updated_by_webhook',
            return_value=False,
        ),
        patch('app.database.crud.subscription.expire_subscription', AsyncMock()),
        patch('app.services.monitoring_service.get_user_by_id', AsyncMock(return_value=user)),
        patch('app.services.monitoring_service.notification_sent', AsyncMock(return_value=True)),
        patch('app.services.monitoring_service.record_notification', AsyncMock()) as record_mock,
        patch.object(service, '_log_monitoring_event', AsyncMock()),
    ):
        await service._check_expired_subscriptions(db)

    service._send_subscription_expired_notification.assert_not_awaited()
    record_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_notify_limiter_in_memory_fallback_when_redis_unavailable():
    limiter = MonitoringNotifyLimiter()

    with patch('app.services.monitoring_notify_limiter.cache.get', AsyncMock(side_effect=Exception('redis down'))):
        with patch('app.services.monitoring_notify_limiter.cache.set', AsyncMock(side_effect=Exception('redis down'))):
            for _ in range(5):
                assert await limiter.can_send_to_user(42) is True
                await limiter.record_send(42)

            assert await limiter.can_send_to_user(42) is False


@pytest.mark.asyncio
async def test_count_notifications_helpers():
    from app.database.crud.notification import count_notifications, count_user_notifications_since

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=2)))

    assert await count_notifications(db, 10, 'traffic_warn') == 2
    since = datetime.now(UTC) - timedelta(days=1)
    assert await count_user_notifications_since(db, 1, since=since, types=('traffic_warn',)) == 2

    db.execute.assert_awaited()
