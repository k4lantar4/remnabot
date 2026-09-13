"""Pure helpers behind multi-subscription reminders (plan 2026-09-12 notifications, task 8).

A user holding many subscriptions got one Telegram message per subscription per checkpoint
(13 "expiring" messages in two days for one test user). These helpers group, cut off abandoned
subscriptions, decide quiet hours and render the one digest message a user gets instead.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace

import pytest

from app.config import QuietHours, Settings
from app.localization.texts import get_texts
from app.services import notification_aggregation as agg


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


def _sub(sub_id: int, *, user_id: int = 1, days: float = 2, tariff: str | None = 'Pro') -> SimpleNamespace:
    return SimpleNamespace(
        id=sub_id,
        user_id=user_id,
        end_date=NOW + timedelta(days=days),
        tariff=SimpleNamespace(name=tariff) if tariff else None,
    )


def _quiet(types: str = 'expiring,expired_followup', start: str = '00:00', end: str = '06:00', enabled=True):
    return Settings.parse_quiet_hours(enabled, start, end, types)


# ---------------------------------------------------------------- grouping and abandonment


def test_collect_user_batches_groups_by_user_and_orders_by_end_date():
    subs = [_sub(1, days=3), _sub(2, user_id=2, days=1), _sub(3, days=1), _sub(4, days=2)]

    batches = agg.collect_user_batches(subs)

    assert list(batches) == [1, 2]
    assert [s.id for s in batches[1]] == [3, 4, 1]
    assert [s.id for s in batches[2]] == [2]


def test_is_abandoned_after_the_cut_off_only():
    assert agg.is_abandoned(_sub(1, days=-8), NOW, 7) is True
    assert agg.is_abandoned(_sub(1, days=-6.9), NOW, 7) is False
    assert agg.is_abandoned(_sub(1, days=1), NOW, 7) is False
    assert agg.is_abandoned(SimpleNamespace(end_date=None), NOW, 7) is False


def test_pick_followup_subscription_takes_the_latest_and_counts_the_others():
    subs = [_sub(1, days=-5), _sub(2, days=-1), _sub(3, days=-3), _sub(4, days=-2)]

    latest, others = agg.pick_followup_subscription(subs)

    assert latest.id == 2
    assert others == 3


# ---------------------------------------------------------------- quiet hours


def test_quiet_hours_parse_defaults_and_ignores_unknown_types():
    quiet = Settings.parse_quiet_hours(True, '00:00', '06:00', 'expiring, bogus ,expired,low_balance')

    assert quiet == QuietHours(True, time(0, 0), time(6, 0), frozenset({'expiring', 'low_balance'}))


def test_quiet_hours_malformed_time_falls_back_to_the_default_window():
    quiet = Settings.parse_quiet_hours(True, '25:99', 'nope', 'expiring')

    assert (quiet.start, quiet.end) == (time(0, 0), time(6, 0))


def test_quiet_hours_default_settings_hold_the_approved_types():
    quiet = Settings().get_quiet_hours()

    assert quiet.enabled is True
    assert (quiet.start, quiet.end) == (time(0, 0), time(6, 0))
    assert quiet.types == frozenset({'expiring', 'expired_followup', 'traffic_warning', 'low_balance', 'daily_charge'})


@pytest.fixture
def tehran(monkeypatch):
    from app.utils import timezone as tz_module

    monkeypatch.setattr(tz_module.settings, 'TIMEZONE', 'Asia/Tehran')
    tz_module.get_local_timezone.cache_clear()
    yield
    tz_module.get_local_timezone.cache_clear()


def test_quiet_hours_hold_at_01_00_tehran_but_not_exempt_types(tehran):
    one_am_tehran = datetime(2026, 9, 12, 21, 30, tzinfo=UTC)  # 01:00 +03:30
    quiet = _quiet()

    assert agg.should_hold_for_quiet_hours('expiring', one_am_tehran, quiet) is True
    assert agg.should_hold_for_quiet_hours('expired', one_am_tehran, quiet) is False
    assert agg.should_hold_for_quiet_hours('traffic_warning', one_am_tehran, quiet) is False


def test_quiet_hours_release_after_the_window(tehran):
    ten_past_six_tehran = datetime(2026, 9, 13, 2, 40, tzinfo=UTC)  # 06:10 +03:30

    assert agg.should_hold_for_quiet_hours('expiring', ten_past_six_tehran, _quiet()) is False


def test_quiet_hours_window_crossing_midnight(tehran):
    quiet = _quiet(start='22:00', end='07:00')
    at = lambda hh, mm: datetime(2026, 9, 13, hh, mm, tzinfo=UTC) - timedelta(hours=3, minutes=30)  # noqa: E731

    assert agg.should_hold_for_quiet_hours('expiring', at(23, 0), quiet) is True
    assert agg.should_hold_for_quiet_hours('expiring', at(6, 59), quiet) is True
    assert agg.should_hold_for_quiet_hours('expiring', at(7, 0), quiet) is False
    assert agg.should_hold_for_quiet_hours('expiring', at(21, 59), quiet) is False


def test_quiet_hours_empty_types_or_disabled_hold_nothing(tehran):
    one_am_tehran = datetime(2026, 9, 12, 21, 30, tzinfo=UTC)

    assert agg.should_hold_for_quiet_hours('expiring', one_am_tehran, _quiet(types='')) is False
    assert agg.should_hold_for_quiet_hours('expiring', one_am_tehran, _quiet(enabled=False)) is False


# ---------------------------------------------------------------- digest rendering


@pytest.fixture
def multi_tariff_cabinet(monkeypatch):
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    monkeypatch.setattr(Settings, 'is_cabinet_mode', lambda self: True)
    from app.config import settings

    monkeypatch.setattr(settings, 'MINIAPP_CUSTOM_URL', 'https://panel.example.com', raising=False)


def _buttons(keyboard) -> list:
    return [button for row in keyboard.inline_keyboard for button in row]


def test_expiring_digest_lists_five_then_more_with_prices_and_jalali_dates(multi_tariff_cabinet):
    texts = get_texts('fa')
    user = SimpleNamespace(id=1, language='fa')
    subs = [_sub(i, days=1 + i / 10, tariff=f'T{i}') for i in range(1, 8)]
    quotes = {s.id: 10_000 for s in subs}
    quotes[7] = None

    text, keyboard = agg.build_expiring_digest(texts, user, subs, quotes, days=3, limit=5)

    for i in range(1, 6):
        assert f'T{i}' in text
    assert 'T6' not in text and 'T7' not in text
    assert texts.t('NOTIFY_DIGEST_MORE').format(count=2) in text
    assert settings_price(10_000) in text
    assert '1405' in text  # Jalali year for a fa reader
    urls = [b.web_app.url for b in _buttons(keyboard) if b.web_app]
    assert 'https://panel.example.com/subscriptions' in urls
    assert 'https://panel.example.com/balance/top-up' in urls


def test_expired_digest_lists_each_subscription(multi_tariff_cabinet):
    texts = get_texts('en')
    user = SimpleNamespace(id=1, language='en')
    subs = [_sub(1, days=0, tariff='A'), _sub(2, days=0, tariff=None)]

    text, keyboard = agg.build_expired_digest(texts, user, subs, limit=5)

    assert 'A' in text and '#2' in text
    assert texts.t('NOTIFY_DIGEST_EXPIRED').split('{')[0].strip() in text
    assert _buttons(keyboard)


def test_other_expired_line_only_when_there_are_others():
    texts = get_texts('en')

    assert agg.other_expired_line(texts, 0) == ''
    assert '3' in agg.other_expired_line(texts, 3)


def test_daily_charge_digest_names_each_charge_total_and_balance():
    texts = get_texts('en')
    charges = [('Daily A', 1_000), ('Daily B', 2_500)]

    text = agg.build_daily_charge_digest(texts, charges, balance=50_000, limit=5)

    assert 'Daily A' in text and 'Daily B' in text
    assert settings_price(3_500) in text
    assert settings_price(50_000) in text


def test_traffic_digest_names_each_subscription():
    texts = get_texts('en')
    items = [('Pro', 9.5, 10, 95.0), ('Lite', 4.1, 5, 82.0)]

    text = agg.build_traffic_digest(texts, items, limit=5)

    assert 'Pro' in text and 'Lite' in text and '95%' in text


def test_autopay_failed_digest_totals_what_is_required(multi_tariff_cabinet):
    texts = get_texts('en')
    user = SimpleNamespace(id=1, language='en')
    items = [
        agg.AutopayFailure(1, 'Pro', NOW + timedelta(days=1), 10_000, False),
        agg.AutopayFailure(2, 'Lite', NOW + timedelta(days=2), 5_000, True),
    ]

    text, keyboard = agg.build_autopay_failed_digest(texts, user, items, balance=1_000, limit=5)

    assert 'Pro' in text and 'Lite' in text
    assert settings_price(15_000) in text
    assert settings_price(1_000) in text
    assert _buttons(keyboard)


def settings_price(amount: int) -> str:
    from app.config import settings

    return settings.format_price(amount)
