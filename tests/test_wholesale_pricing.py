"""Tests for DB-driven partner wholesale pricing (integer BPS)."""

from unittest.mock import MagicMock

import pytest

from app.database.models import PartnerStatus
from app.services.pricing_engine import PricingEngine


def _partner_user(*, bps: int = 2500) -> MagicMock:
    user = MagicMock()
    user.partner_status = PartnerStatus.APPROVED.value
    user.is_partner = True
    user.wholesale_discount_bps = bps
    return user


class TestWholesaleBpsHelpers:
    def test_apply_wholesale_25_percent(self):
        user = _partner_user(bps=2500)
        final, discount = PricingEngine.apply_wholesale_discount(10000, user)
        assert final == 7500
        assert discount == 2500

    def test_apply_wholesale_matches_float_formula(self):
        user = _partner_user(bps=3333)
        subtotal = 99900
        final, _ = PricingEngine.apply_wholesale_discount(subtotal, user)
        expected = int(subtotal * (1.0 - 3333 / 10000.0))
        assert final == expected

    def test_non_partner_no_discount(self):
        user = MagicMock(is_partner=False, wholesale_discount_bps=2500)
        final, discount = PricingEngine.apply_wholesale_discount(10000, user)
        assert final == 10000
        assert discount == 0

    def test_partner_zero_bps_no_discount(self):
        user = _partner_user(bps=0)
        assert PricingEngine.uses_wholesale_pricing(user) is False
        final, discount = PricingEngine.apply_wholesale_discount(10000, user)
        assert final == 10000
        assert discount == 0

    def test_bps_clamped_to_10000(self):
        user = _partner_user(bps=15000)
        assert PricingEngine.get_wholesale_discount_bps(user) == 10000
        final, discount = PricingEngine.apply_wholesale_discount(10000, user)
        assert final == 0
        assert discount == 10000


class TestWholesaleTrafficDiscount:
    def test_traffic_topup_uses_wholesale_not_promo_group(self):
        user = _partner_user(bps=2000)
        final, discount, pct = PricingEngine.calculate_traffic_discount(50000, user)
        assert final == 40000
        assert discount == 10000
        assert pct == 20

    def test_retail_user_unchanged_without_group(self):
        user = MagicMock(is_partner=False, wholesale_discount_bps=0)
        user.get_primary_promo_group = MagicMock(return_value=None)
        user.promo_group = None
        final, discount, pct = PricingEngine.calculate_traffic_discount(50000, user)
        assert final == 50000
        assert discount == 0
        assert pct == 0


class TestWholesaleTariffCore:
    @pytest.mark.asyncio
    async def test_tariff_purchase_bypasses_retail_stack(self):
        engine = PricingEngine()
        tariff = MagicMock()
        tariff.id = 1
        tariff.is_daily = False
        tariff.period_prices = {'30': 100000}
        tariff.device_limit = 1
        tariff.device_price_kopeks = 0
        tariff.custom_traffic_enabled = False
        tariff.can_purchase_custom_traffic = MagicMock(return_value=False)
        tariff.is_available_for_promo_group = MagicMock(return_value=True)

        user = _partner_user(bps=2500)
        promo_group = MagicMock()
        promo_group.get_discount_percent = MagicMock(return_value=50)
        user.get_primary_promo_group = MagicMock(return_value=promo_group)
        user.promo_group = None

        result = await engine._calculate_tariff_core(tariff, 30, 1, user=user)

        assert result.final_total == 75000
        assert result.promo_offer_discount == 0
        assert result.promo_group_discount == 25000
        assert result.breakdown.get('wholesale_applied') is True
        assert result.breakdown.get('wholesale_discount_bps') == 2500


class TestWholesaleDisplayParity:
    def test_calculate_user_price_matches_wholesale_discount(self):
        from app.utils.price_display import calculate_user_price

        user = _partner_user(bps=2500)
        base_price = 100000
        price_info = calculate_user_price(user, base_price, 30, 'period')
        expected_final, _ = PricingEngine.apply_wholesale_discount(base_price, user)
        assert price_info.final_price == expected_final
        assert price_info.base_price == base_price

    def test_apply_checkout_discount_wholesale_path(self):
        user = _partner_user(bps=2000)
        final, primary, secondary = PricingEngine.apply_checkout_discount(50000, user)
        assert final == 40000
        assert primary == 10000
        assert secondary == 0

    def test_apply_checkout_discount_retail_path(self):
        user = MagicMock(is_partner=False, wholesale_discount_bps=0)
        final, primary, secondary = PricingEngine.apply_checkout_discount(10000, user, group_pct=10, offer_pct=0)
        assert final == 9000
        assert primary == 1000
        assert secondary == 0
