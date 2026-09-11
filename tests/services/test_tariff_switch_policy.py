"""Правила смены тарифа: остаток к оплате и обнуление трафика.

Отчёт из «Багов»: «если в подписке осталось 0 дней, можно прыгать между
тарифами бесплатно + трафик сбрасывается из-за этого».
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.database.models import Tariff
from app.services.tariff_switch_policy import (
    is_switch_direction_allowed,
    remaining_days_for_switch,
    should_reset_used_traffic,
    switch_direction_refusal,
    tariff_switch_allowed,
)


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ('end_date', 'expected'),
    [
        (NOW + timedelta(minutes=1), 1),
        (NOW + timedelta(hours=5), 1),
        (NOW + timedelta(hours=23, minutes=59), 1),
        (NOW + timedelta(days=1), 1),
        (NOW + timedelta(days=1, hours=12), 1),
        (NOW + timedelta(days=29, hours=23), 29),
        (NOW + timedelta(days=30), 30),
    ],
)
def test_live_subscription_costs_at_least_one_day(end_date, expected):
    """Остаток в часах — не ноль: иначе переключение бесплатное."""
    assert remaining_days_for_switch(end_date, NOW) == expected


@pytest.mark.parametrize(
    'end_date',
    [None, NOW, NOW - timedelta(seconds=1), NOW - timedelta(days=3)],
)
def test_expired_subscription_has_no_remaining_days(end_date):
    """Истёкшей подписке путь в покупку, а не в переключение."""
    assert remaining_days_for_switch(end_date, NOW) == 0


def test_naive_datetime_is_treated_as_utc():
    """SQLite отдаёт даты без таймзоны — сравнение не должно падать."""
    assert remaining_days_for_switch(datetime(2026, 9, 10, 12, 0), NOW) == 2


def test_defaults_to_current_time():
    assert remaining_days_for_switch(datetime.now(UTC) + timedelta(hours=2)) == 1
    assert remaining_days_for_switch(datetime.now(UTC) - timedelta(hours=2)) == 0


class TestTrafficReset:
    def test_paid_switch_resets(self, monkeypatch):
        monkeypatch.setattr(settings, 'RESET_TRAFFIC_ON_TARIFF_SWITCH', True)
        assert should_reset_used_traffic(1) is True
        assert should_reset_used_traffic(500_00) is True

    def test_free_switch_keeps_used_traffic(self, monkeypatch):
        """Иначе понизил тариф — счётчик с нуля, вернулся — ещё раз."""
        monkeypatch.setattr(settings, 'RESET_TRAFFIC_ON_TARIFF_SWITCH', True)
        assert should_reset_used_traffic(0) is False

    def test_global_switch_off_wins(self, monkeypatch):
        monkeypatch.setattr(settings, 'RESET_TRAFFIC_ON_TARIFF_SWITCH', False)
        assert should_reset_used_traffic(500_00) is False
        assert should_reset_used_traffic(0) is False


def _tariff(tariff_id: int, monthly: int) -> Tariff:
    return Tariff(
        id=tariff_id,
        name=f'T{tariff_id}',
        is_active=True,
        is_daily=False,
        period_prices={'30': monthly},
        daily_price_kopeks=0,
        traffic_limit_gb=0,
        device_limit=1,
    )


class TestSwitchDirection:
    """Кабинет спрашивает то же правило, что и список смены в боте (F-001)."""

    @pytest.mark.parametrize(
        ('upgrade_ok', 'downgrade_ok', 'is_upgrade', 'expected'),
        [
            (True, True, True, True),
            (True, True, False, True),
            (True, False, True, True),
            (True, False, False, False),
            (False, True, True, False),
            (False, True, False, True),
        ],
    )
    def test_direction_follows_settings(self, monkeypatch, upgrade_ok, downgrade_ok, is_upgrade, expected):
        monkeypatch.setattr(settings, 'TARIFF_SWITCH_UPGRADE_ENABLED', upgrade_ok)
        monkeypatch.setattr(settings, 'TARIFF_SWITCH_DOWNGRADE_ENABLED', downgrade_ok)
        assert is_switch_direction_allowed(is_upgrade) is expected

    def test_refusal_carries_a_code(self):
        assert switch_direction_refusal(True)['code'] == 'tariff_upgrade_disabled'
        assert switch_direction_refusal(False)['code'] == 'tariff_downgrade_disabled'
        assert switch_direction_refusal(False)['message']

    def test_equal_price_counts_as_downgrade(self, monkeypatch):
        """Тарифы 2 и 4 стоят одинаково: доплаты нет — это понижение."""
        monkeypatch.setattr(settings, 'TARIFF_SWITCH_UPGRADE_ENABLED', True)
        monkeypatch.setattr(settings, 'TARIFF_SWITCH_DOWNGRADE_ENABLED', False)
        assert tariff_switch_allowed(_tariff(2, 20000), _tariff(4, 20000), 20) is False
        assert tariff_switch_allowed(_tariff(2, 20000), _tariff(5, 10000), 20) is False
        assert tariff_switch_allowed(_tariff(2, 20000), _tariff(6, 40000), 20) is True

    def test_both_directions_enabled_skips_pricing(self, monkeypatch):
        monkeypatch.setattr(settings, 'TARIFF_SWITCH_UPGRADE_ENABLED', True)
        monkeypatch.setattr(settings, 'TARIFF_SWITCH_DOWNGRADE_ENABLED', True)
        assert tariff_switch_allowed(_tariff(2, 20000), _tariff(4, 20000), 20) is True
