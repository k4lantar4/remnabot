"""Reminders for users holding many subscriptions: one message per user (plan 2026-09-12 notifications, task 8).

Dev DB, 2026-09-12: user 433 (39 active subscriptions) received 13 separate "expiring" messages in two
days, and a user whose subscriptions had all lapsed got the expired-1d + two winback messages — and a
new discount offer — for every one of them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.database.models import (
    DiscountOffer,
    PromoGroup,
    SentNotification,
    Subscription,
    SubscriptionStatus,
    Tariff,
    User,
    UserStatus,
)
from app.localization.texts import get_texts
from app.services import daily_subscription_service as daily_module, monitoring_service
from app.services.monitoring_service import MonitoringService
from app.services.notification_settings_service import NotificationSettingsService
from tests.fixtures.sqlite_memory import memory_session


NOW = datetime.now(UTC)


@pytest.fixture(autouse=True)
def _notifications_on(monkeypatch):
    monkeypatch.setattr(
        NotificationSettingsService, 'are_notifications_globally_enabled', classmethod(lambda cls: True)
    )
    monkeypatch.setattr(MonitoringService, '_held_for_quiet_hours', staticmethod(lambda notice_type: False))
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)


def _service() -> MonitoringService:
    service = MonitoringService.__new__(MonitoringService)
    service.bot = SimpleNamespace(send_message=AsyncMock())
    service._log_monitoring_event = AsyncMock()
    return service


# ---------------------------------------------------------------- expiring (R2.1, R2.2, R2.6)


def _user(balance: int = 50_000) -> SimpleNamespace:
    return SimpleNamespace(
        id=433, telegram_id=433433, language='fa', balance_kopeks=balance, status='active', notification_settings={}
    )


def _expiring(sub_id: int, user, days: float, *, autopay: bool = False, tariff: str = 'Pro') -> SimpleNamespace:
    return SimpleNamespace(
        id=sub_id,
        user_id=user.id,
        user=user,
        end_date=NOW + timedelta(days=days),
        autopay_enabled=autopay,
        tariff=SimpleNamespace(name=tariff),
    )


@pytest.fixture
def expiring_env(monkeypatch):
    sent: set[tuple[int, str, int | None]] = set()

    async def notification_sent(db, user_id, subscription_id, kind, days=None):
        return (subscription_id, kind, days) in sent

    async def record_notification(db, user_id, subscription_id, kind, days=None, **_):
        sent.add((subscription_id, kind, days))

    monkeypatch.setattr(monitoring_service, 'notification_sent', notification_sent)
    monkeypatch.setattr(monitoring_service, 'record_notification', record_notification)
    monkeypatch.setattr(Settings, 'get_autopay_warning_days', lambda self: [3, 1])

    service = _service()
    service._send_digest = AsyncMock(return_value=True)
    service._send_subscription_expiring_notification = AsyncMock(return_value=True)
    service._quote_renewal_price = AsyncMock(return_value=10_000)

    def use(subscriptions):
        async def expiring(db, days):
            return [s for s in subscriptions if s.end_date <= NOW + timedelta(days=days)]

        service._get_expiring_paid_subscriptions = expiring
        return service

    return use, sent


async def test_seven_subscriptions_expiring_in_three_days_make_one_message(expiring_env):
    use, sent = expiring_env
    user = _user()
    subscriptions = [_expiring(i, user, 1.5 + i * 0.1, tariff=f'T{i}') for i in range(1, 8)]
    service = use(subscriptions)

    await service._check_expiring_subscriptions(db=None)

    service._send_digest.assert_awaited_once()
    text = service._send_digest.await_args.args[1]
    assert all(f'T{i}' in text for i in range(1, 6))
    assert 'T6' not in text and 'T7' not in text
    assert get_texts('fa').t('NOTIFY_DIGEST_MORE').format(count=2) in text
    assert sent == {(i, 'expiring', 3) for i in range(1, 8)}

    await service._check_expiring_subscriptions(db=None)

    service._send_digest.assert_awaited_once()
    service._send_subscription_expiring_notification.assert_not_awaited()


async def test_a_subscription_is_listed_only_at_its_most_urgent_checkpoint(expiring_env):
    use, sent = expiring_env
    user = _user()
    urgent, later = _expiring(1, user, 0.5), _expiring(2, user, 2)
    service = use([urgent, later])

    await service._check_expiring_subscriptions(db=None)

    calls = service._send_subscription_expiring_notification.await_args_list
    assert [(c.args[1].id, c.args[2]) for c in calls] == [(1, 1), (2, 3)]
    assert [c.kwargs['quote'] for c in calls] == [10_000, 10_000]
    assert sent == {(1, 'expiring', 1), (2, 'expiring', 3)}
    service._send_digest.assert_not_awaited()


async def test_autopay_with_enough_balance_is_not_reminded(expiring_env):
    use, sent = expiring_env
    user = _user(balance=50_000)
    covered = _expiring(1, user, 2, autopay=True)
    short = _expiring(2, user, 2, autopay=True)
    manual = _expiring(3, user, 2)
    service = use([covered, short, manual])
    service._quote_renewal_price = AsyncMock(
        side_effect=lambda db, sub, user: {1: 10_000, 2: 90_000, 3: 10_000}[sub.id]
    )

    await service._check_expiring_subscriptions(db=None)

    listed = service._send_digest.await_args.args[1]
    assert sent == {(2, 'expiring', 3), (3, 'expiring', 3)}
    assert listed.count('Pro') == 2


async def test_held_expiring_reminder_touches_nothing(expiring_env, monkeypatch):
    use, sent = expiring_env
    user = _user()
    service = use([_expiring(1, user, 2), _expiring(2, user, 2)])
    monkeypatch.setattr(MonitoringService, '_held_for_quiet_hours', staticmethod(lambda notice_type: True))

    await service._check_expiring_subscriptions(db=None)

    service._send_digest.assert_not_awaited()
    assert sent == set()


# ---------------------------------------------------------------- autopay failed (R2.1)


async def test_autopay_failures_of_one_user_are_sent_as_one_message(monkeypatch):
    from app.services.notification_aggregation import AutopayFailure

    user = _user(balance=1_000)
    monkeypatch.setattr(monitoring_service, 'get_user_by_id', AsyncMock(return_value=user))
    service = _service()
    service._send_digest = AsyncMock(return_value=True)
    service._send_autopay_failed_notification = AsyncMock()
    pending = [
        (user.id, AutopayFailure(1, 'Pro', NOW + timedelta(days=1), 10_000, False)),
        (user.id, AutopayFailure(2, 'Lite', NOW + timedelta(days=2), 5_000, False)),
    ]

    await service._flush_autopay_failures(db=None, pending=pending)

    service._send_digest.assert_awaited_once()
    text = service._send_digest.await_args.args[1]
    assert 'Pro' in text and 'Lite' in text
    service._send_autopay_failed_notification.assert_not_awaited()

    await service._flush_autopay_failures(db=None, pending=pending[:1])

    service._send_autopay_failed_notification.assert_awaited_once()
    assert service._send_autopay_failed_notification.await_args.kwargs['subscription'].tariff.name == 'Pro'


# ---------------------------------------------------------------- follow-ups (R2.3, R2.4, R2.5), real queries

FOLLOWUP_TABLES = (
    User.__table__,
    Subscription.__table__,
    Tariff.__table__,
    PromoGroup.__table__,
    SentNotification.__table__,
    DiscountOffer.__table__,
)


async def _add_user(db, telegram_id: int) -> User:
    user = User(
        telegram_id=telegram_id,
        username=f'user{telegram_id}',
        first_name='User',
        status=UserStatus.ACTIVE.value,
        balance_kopeks=0,
        language='fa',
    )
    db.add(user)
    await db.commit()
    return user


async def _add_expired(db, user: User, days_ago: float) -> Subscription:
    subscription = Subscription(
        user_id=user.id,
        status=SubscriptionStatus.EXPIRED.value,
        is_trial=False,
        start_date=NOW - timedelta(days=40),
        end_date=NOW - timedelta(days=days_ago),
        remnawave_short_id=f'short{user.id}_{days_ago}',
    )
    db.add(subscription)
    await db.commit()
    return subscription


async def test_followup_runs_once_per_user_for_the_latest_subscription_and_skips_abandoned(monkeypatch):
    async with memory_session(monkeypatch, FOLLOWUP_TABLES) as db:
        user = await _add_user(db, 1)
        latest = await _add_expired(db, user, 1.5)
        await _add_expired(db, user, 1.7)
        await _add_expired(db, user, 1.9)
        await _add_expired(db, user, 8)  # abandoned: expired more than 7 days ago
        service = _service()
        service._send_expired_day1_notification = AsyncMock(return_value=True)
        service._send_expired_discount_notification = AsyncMock(return_value=True)

        await service._check_expired_subscription_followups(db)
        await service._check_expired_subscription_followups(db)

        service._send_expired_day1_notification.assert_awaited_once()
        call = service._send_expired_day1_notification.await_args
        assert call.args[2].id == latest.id
        assert call.kwargs['other_expired_count'] == 2


async def test_abandoned_only_subscription_gets_no_followup(monkeypatch):
    async with memory_session(monkeypatch, FOLLOWUP_TABLES) as db:
        user = await _add_user(db, 1)
        await _add_expired(db, user, 8)
        service = _service()
        service._send_expired_day1_notification = AsyncMock(return_value=True)
        service._send_expired_discount_notification = AsyncMock(return_value=True)

        await service._check_expired_subscription_followups(db)

        service._send_expired_day1_notification.assert_not_awaited()
        service._send_expired_discount_notification.assert_not_awaited()


async def test_second_winback_offer_within_30_days_is_not_made(monkeypatch):
    async with memory_session(monkeypatch, FOLLOWUP_TABLES) as db:
        offered = await _add_user(db, 1)
        earlier = await _add_expired(db, offered, 20)
        await _add_expired(db, offered, 2.5)
        db.add(
            DiscountOffer(
                user_id=offered.id,
                subscription_id=earlier.id,
                notification_type='expired_discount_wave3',
                discount_percent=20,
                expires_at=NOW - timedelta(days=9),
                is_active=False,
                created_at=NOW - timedelta(days=10),
            )
        )
        fresh = await _add_user(db, 2)
        await _add_expired(db, fresh, 2.5)
        await db.commit()
        service = _service()
        service._send_expired_day1_notification = AsyncMock(return_value=True)
        service._send_expired_discount_notification = AsyncMock(return_value=True)

        await service._check_expired_subscription_followups(db)

        calls = service._send_expired_discount_notification.await_args_list
        assert [c.args[0].id for c in calls] == [fresh.id]


# ---------------------------------------------------------------- expired, same cycle (R2.1)


async def test_subscriptions_expiring_in_the_same_cycle_make_one_message(monkeypatch):
    user = SimpleNamespace(id=7, telegram_id=77, language='fa', status='active', notification_settings={})
    subscriptions = [
        SimpleNamespace(id=i, user_id=7, end_date=NOW - timedelta(hours=1), tariff=SimpleNamespace(name=f'T{i}'))
        for i in (1, 2)
    ]
    monkeypatch.setattr(monitoring_service, 'get_expired_subscriptions', AsyncMock(return_value=subscriptions))
    monkeypatch.setattr(monitoring_service, 'get_user_by_id', AsyncMock(return_value=user))
    monkeypatch.setattr('app.database.crud.subscription.is_recently_updated_by_webhook', lambda subscription: False)
    monkeypatch.setattr('app.database.crud.subscription.expire_subscription', AsyncMock())
    no_active = SimpleNamespace(scalar_one_or_none=lambda: None)
    service = _service()
    service._send_digest = AsyncMock(return_value=True)
    service._send_subscription_expired_notification = AsyncMock(return_value=True)

    await service._check_expired_subscriptions(SimpleNamespace(execute=AsyncMock(return_value=no_active)))

    service._send_digest.assert_awaited_once()
    text = service._send_digest.await_args.args[1]
    assert 'T1' in text and 'T2' in text
    service._send_subscription_expired_notification.assert_not_awaited()


# ---------------------------------------------------------------- daily charge (R2.7, R2.8)


class _FakeCache:
    def __init__(self):
        self.store: dict[str, object] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, expire=None):
        self.store[key] = value
        return True

    async def getdel(self, key):
        return self.store.pop(key, None)

    async def get_keys(self, pattern='*'):
        prefix = pattern.rstrip('*')
        return [key for key in self.store if key.startswith(prefix)]


@pytest.fixture
def daily_env(monkeypatch):
    user = SimpleNamespace(id=1, language='en', balance_kopeks=50_000)
    delivery = SimpleNamespace(notify_daily_debit=AsyncMock(), send_notification=AsyncMock())
    fake_cache = _FakeCache()
    holding = {'value': False}
    monkeypatch.setattr(daily_module, 'notification_delivery_service', delivery)
    monkeypatch.setattr(daily_module, 'get_user_by_id', AsyncMock(return_value=user))
    monkeypatch.setattr(daily_module, 'cache', fake_cache)
    monkeypatch.setattr(daily_module, 'should_hold_for_quiet_hours', lambda *args: holding['value'])
    service = daily_module.DailySubscriptionService()
    service._bot = object()
    return service, delivery, holding


async def test_daily_charges_of_one_run_make_one_message(daily_env):
    service, delivery, _ = daily_env

    await service._flush_daily_charge_notices(None, {1: [('Daily A', 1_000), ('Daily B', 2_500)]})

    delivery.notify_daily_debit.assert_awaited_once()
    kwargs = delivery.notify_daily_debit.await_args.kwargs
    assert 'Daily A' in kwargs['telegram_message'] and 'Daily B' in kwargs['telegram_message']
    assert kwargs['amount_kopeks'] == 3_500


async def test_daily_charges_held_in_quiet_hours_are_sent_with_the_next_run(daily_env):
    service, delivery, holding = daily_env
    holding['value'] = True

    await service._flush_daily_charge_notices(None, {1: [('Daily A', 1_000), ('Daily B', 2_500)]})

    delivery.notify_daily_debit.assert_not_awaited()

    holding['value'] = False
    await service._flush_daily_charge_notices(None, {1: [('Daily C', 500)]})

    delivery.notify_daily_debit.assert_awaited_once()
    message = delivery.notify_daily_debit.await_args.kwargs['telegram_message']
    assert all(name in message for name in ('Daily A', 'Daily B', 'Daily C'))
