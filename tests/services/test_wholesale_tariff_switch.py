"""F-029 / plan 2026-09-11 Task 2: every tariff-switch branch takes the wholesale rate.

An approved partner's wholesale discount replaces the promo-group discount and the promo
offer (the rule of ``_calculate_tariff_core``). Before this, all three paid switch branches
charged a partner the retail price minus group and offer. Amounts are Toman 1:1.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.database.models import PartnerStatus, Tariff
from app.services.pricing_engine import PricingEngine


def _user(*, partner_status: str = PartnerStatus.NONE.value, bps: int = 0, group_pct: int = 10, offer_pct: int = 20):
    group = SimpleNamespace(id=7, name='g', get_discount_percent=lambda _cat, _days: group_pct)
    return SimpleNamespace(
        id=1,
        partner_status=partner_status,
        wholesale_discount_bps=bps,
        promo_group=None,
        get_primary_promo_group=lambda: group if group_pct else None,
        promo_offer_discount_percent=offer_pct,
        promo_offer_discount_expires_at=datetime.now(UTC) + timedelta(days=1),
        promo_offer_discount_source='test',
    )


def _partner(**kwargs):
    return _user(partner_status=PartnerStatus.APPROVED.value, bps=3000, **kwargs)


def _periodic(tariff_id: int, prices: dict[str, int]) -> Tariff:
    return Tariff(
        id=tariff_id,
        name=f't{tariff_id}',
        is_active=True,
        is_daily=False,
        daily_price_kopeks=0,
        period_prices=prices,
        traffic_limit_gb=10,
        device_limit=1,
        allowed_squads=[],
        display_order=1,
    )


def _daily(tariff_id: int = 9, price: int = 10_000) -> Tariff:
    return Tariff(
        id=tariff_id,
        name='روزانه',
        is_active=True,
        is_daily=True,
        daily_price_kopeks=price,
        period_prices={},
        traffic_limit_gb=10,
        device_limit=1,
        allowed_squads=[],
        display_order=1,
    )


ENGINE = PricingEngine()


class TestPeriodicToDaily:
    def test_partner_with_offer_pays_wholesale_first_day(self):
        result = ENGINE.calculate_tariff_switch_cost(_periodic(2, {'30': 30_000}), _daily(), 10, user=_partner())
        assert result.upgrade_cost == 7_000
        assert result.raw_cost == 10_000
        assert (result.group_discount_pct, result.offer_discount_pct) == (0, 0)
        assert result.effective_discount_pct == 30

    def test_b2c_unchanged(self):
        result = ENGINE.calculate_tariff_switch_cost(_periodic(2, {'30': 30_000}), _daily(), 10, user=_user())
        assert result.upgrade_cost == 7_200  # 10,000 − 10% group − 20% offer
        assert (result.group_discount_pct, result.offer_discount_pct) == (10, 20)


class TestDailyToPeriodic:
    def test_partner_pays_wholesale_min_period(self):
        new = _periodic(2, {'30': 60_000, '90': 150_000})
        result = ENGINE.calculate_tariff_switch_cost(_daily(), new, 1, user=_partner())
        assert result.upgrade_cost == 42_000
        assert result.raw_cost == 60_000
        assert (result.group_discount_pct, result.offer_discount_pct) == (0, 0)
        assert result.new_period_days == 30

    def test_b2c_unchanged(self):
        new = _periodic(2, {'30': 60_000, '90': 150_000})
        result = ENGINE.calculate_tariff_switch_cost(_daily(), new, 1, user=_user())
        assert result.upgrade_cost == 43_200


class TestPeriodicToPeriodic:
    def test_partner_upgrade_is_wholesale_of_raw_cost(self):
        cur, new = _periodic(2, {'30': 30_000}), _periodic(4, {'30': 60_000})
        result = ENGINE.calculate_tariff_switch_cost(cur, new, 15, user=_partner())
        assert result.raw_cost == 15_000
        assert result.upgrade_cost == 15_000 * (10000 - 3000) // 10000
        assert (result.group_discount_pct, result.offer_discount_pct) == (0, 0)
        assert result.is_upgrade is True

    def test_b2c_unchanged(self):
        cur, new = _periodic(2, {'30': 30_000}), _periodic(4, {'30': 60_000})
        result = ENGINE.calculate_tariff_switch_cost(cur, new, 15, user=_user())
        assert result.upgrade_cost == 10_800
        assert (result.group_discount_pct, result.offer_discount_pct) == (10, 20)

    def test_partner_downgrade_still_free(self):
        cur, new = _periodic(4, {'30': 60_000}), _periodic(2, {'30': 30_000})
        result = ENGINE.calculate_tariff_switch_cost(cur, new, 15, user=_partner())
        assert result.upgrade_cost == 0


def test_daily_to_daily_still_free_for_partner():
    result = ENGINE.calculate_tariff_switch_cost(_daily(9), _daily(10, 20_000), 1, user=_partner())
    assert result.upgrade_cost == 0
