"""F-001: purchase-options говорит кабинету, пропустит ли бот смену на тариф.

Тарифы 2 и 4 стоят одинаково, понижение выключено. Кабинет показывал
«Сменить», а превью отвечало 403 «Понижение тарифа недоступно»: направление
считает бот (доплата > 0 — повышение), кабинет его не знал.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.cabinet.routes.subscription_modules.purchase import _switch_allowed_for
from app.config import settings
from app.database.models import Tariff


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


CURRENT = _tariff(2, 20000)


def _sub(status: str = 'active') -> SimpleNamespace:
    return SimpleNamespace(
        tariff_id=CURRENT.id,
        actual_status=status,
        end_date=datetime.now(UTC) + timedelta(days=20),
    )


@pytest.fixture
def downgrade_off(monkeypatch):
    monkeypatch.setattr(settings, 'TARIFF_SWITCH_UPGRADE_ENABLED', True)
    monkeypatch.setattr(settings, 'TARIFF_SWITCH_DOWNGRADE_ENABLED', False)


@pytest.mark.usefixtures('downgrade_off')
class TestSwitchAllowed:
    def test_equal_price_is_blocked(self):
        assert _switch_allowed_for(_tariff(4, 20000), CURRENT, _sub(), None) is False

    def test_cheaper_is_blocked(self):
        assert _switch_allowed_for(_tariff(5, 10000), CURRENT, _sub(), None) is False

    def test_more_expensive_is_allowed(self):
        assert _switch_allowed_for(_tariff(6, 40000), CURRENT, _sub(), None) is True

    def test_current_tariff_is_not_judged(self):
        assert _switch_allowed_for(CURRENT, CURRENT, _sub(), None) is True

    def test_no_subscription_or_tariff(self):
        assert _switch_allowed_for(_tariff(4, 20000), None, None, None) is True
        assert _switch_allowed_for(_tariff(4, 20000), None, _sub(), None) is True

    @pytest.mark.parametrize('status', ['expired', 'trial', 'disabled'])
    def test_not_switchable_subscription_is_not_judged(self, status):
        """Истёкшая/пробная идёт в покупку — направление к ней не относится."""
        assert _switch_allowed_for(_tariff(4, 20000), CURRENT, _sub(status), None) is True


def test_both_directions_enabled(monkeypatch):
    monkeypatch.setattr(settings, 'TARIFF_SWITCH_UPGRADE_ENABLED', True)
    monkeypatch.setattr(settings, 'TARIFF_SWITCH_DOWNGRADE_ENABLED', True)
    assert _switch_allowed_for(_tariff(4, 20000), CURRENT, _sub(), None) is True
