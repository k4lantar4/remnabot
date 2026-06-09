"""Tests for tools/tariff_price_refactor.py and custom-traffic pricing."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.pricing_engine import PricingEngine
from app.utils.pricing_utils import calculate_months_from_days
from tools.tariff_price_refactor import (
    PRICE_PER_GB_KOPEKS,
    build_tariff_price_patches,
    build_traffic_packages_env,
    recalc_traffic_topup_packages,
    target_monthly_kopeks,
    zero_period_prices,
)


def _row(
    tariff_id: int = 1,
    traffic_gb: int = 10,
    period_prices: dict | None = None,
    topup: dict | None = None,
    custom_traffic_enabled: bool = False,
) -> dict:
    return {
        'id': tariff_id,
        'name': 'پریمیوم',
        'traffic_limit_gb': traffic_gb,
        'period_prices': period_prices
        or {'14': 700000, '30': 1000000, '60': 2590000, '90': 3690000, '180': 6990000, '360': 10990000},
        'traffic_topup_packages': topup or {'10': 10000},
        'traffic_price_per_gb_kopeks': 0,
        'custom_traffic_enabled': custom_traffic_enabled,
        'min_traffic_gb': 10,
    }


def test_target_monthly_10gb():
    assert target_monthly_kopeks(10) == 10_000_000


def test_zero_period_prices():
    old = {'14': 700000, '30': 1000000, '60': 2590000}
    assert zero_period_prices(old) == {'14': 0, '30': 0, '60': 0}


def test_recalc_traffic_topup_linear_per_gb():
    assert recalc_traffic_topup_packages({'5': 20000, '10': 10000}) == {'5': 5_000_000, '10': 10_000_000}


def test_build_patches_enables_custom_traffic():
    patches = build_tariff_price_patches([_row()])
    assert len(patches) == 1
    assert patches[0]['changed'] is True
    assert patches[0]['new_custom_traffic_enabled'] is True
    assert patches[0]['new_period_prices']['30'] == 0
    assert patches[0]['new_traffic_price_per_gb_kopeks'] == PRICE_PER_GB_KOPEKS
    assert patches[0]['new_min_traffic_gb'] == 1


def test_build_patches_idempotent_when_already_correct():
    period = zero_period_prices(_row()['period_prices'])
    topup = recalc_traffic_topup_packages({'10': 10000})
    already = _row(
        period_prices=period,
        topup=topup,
        custom_traffic_enabled=True,
    )
    already['traffic_price_per_gb_kopeks'] = PRICE_PER_GB_KOPEKS
    already['min_traffic_gb'] = 1
    patches = build_tariff_price_patches([already])
    assert patches[0]['changed'] is False


def test_traffic_packages_env_uses_10000_per_gb():
    env = build_traffic_packages_env()
    assert '5:5000000:false' in env
    assert '10:10000000:false' in env
    assert '0:10000000:true' in env


def test_custom_traffic_10gb_30d_equals_10m_kopeks():
    """10 GB × 30 days × 1M kopeks/GB/month = 10_000_000 kopeks."""
    per_gb = PRICE_PER_GB_KOPEKS
    traffic_gb = 10
    days = 30
    months = calculate_months_from_days(days)
    assert per_gb * traffic_gb * months == 10_000_000


def test_partner_50pct_traffic_discount():
    """Partner promo group 50% traffic discount → 5_000_000 kopeks for 10GB/30d."""
    base_traffic = 10_000_000
    final, discount_value, pct = PricingEngine.calculate_traffic_discount(
        base_traffic,
        MagicMock(
            promo_group=MagicMock(
                apply_discounts_to_addons=True,
                get_discount_percent=MagicMock(return_value=50),
            ),
            get_primary_promo_group=MagicMock(return_value=MagicMock(
                apply_discounts_to_addons=True,
                get_discount_percent=MagicMock(return_value=50),
            )),
        ),
    )
    assert pct == 50
    assert final == 5_000_000
    assert discount_value == 5_000_000
