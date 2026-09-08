"""M6-T3 G10: wholesale pricing regression gate.

remnabot already has tests/test_wholesale_pricing.py (ported in M4-T7).
This file is the named M6-T3 gate. It locks:

- Gating on partner_status + wholesale_discount_bps via the ported
  remnabot price_display path / PricingEngine (not app.custom.pricing).
- Integer BPS with floor division.
- Approved partner discounted; non-approved (rejected/pending/none) not.

PartnerStatus has no REVOKED member; REJECTED is the production revoke.
"""

from __future__ import annotations

import importlib.util
from types import SimpleNamespace

from app.database.models import PartnerStatus
from app.services.pricing_engine import PricingEngine
from app.utils.price_display import calculate_user_price


def _user(*, status: str, bps: int = 2500, promo_percent: int = 0) -> SimpleNamespace:
    """Stub with partner_status only — do not set is_partner."""
    return SimpleNamespace(
        partner_status=status,
        wholesale_discount_bps=bps,
        telegram_id=1,
        get_promo_discount=lambda category, period_days: promo_percent,
    )


def test_approved_partner_discounted_integer_bps_floor():
    user = _user(status=PartnerStatus.APPROVED.value, bps=3333)
    subtotal = 9999
    final, discount = PricingEngine.apply_wholesale_discount(subtotal, user)
    expected = subtotal * (10000 - 3333) // 10000
    assert expected == 6666
    assert final == expected
    assert discount == subtotal - expected
    assert PricingEngine.uses_wholesale_pricing(user) is True


def test_approved_partner_25_percent():
    user = _user(status=PartnerStatus.APPROVED.value, bps=2500)
    final, discount = PricingEngine.apply_wholesale_discount(10000, user)
    assert final == 7500
    assert discount == 2500


def test_rejected_partner_not_discounted_even_with_bps():
    user = _user(status=PartnerStatus.REJECTED.value, bps=2500)
    assert PricingEngine.uses_wholesale_pricing(user) is False
    assert PricingEngine.get_wholesale_discount_bps(user) == 0
    final, discount = PricingEngine.apply_wholesale_discount(10000, user)
    assert final == 10000
    assert discount == 0


def test_pending_and_none_not_discounted():
    for status in (PartnerStatus.PENDING.value, PartnerStatus.NONE.value):
        user = _user(status=status, bps=2500)
        assert PricingEngine.uses_wholesale_pricing(user) is False
        final, discount = PricingEngine.apply_wholesale_discount(10000, user)
        assert final == 10000, status
        assert discount == 0, status


def test_price_display_approved_bypasses_retail_promo():
    user = _user(status=PartnerStatus.APPROVED.value, bps=2500, promo_percent=50)
    info = calculate_user_price(user, 10000, 30, 'period')
    assert info.final_price == 7500
    assert info.base_price == 10000


def test_price_display_rejected_uses_retail_not_wholesale():
    user = _user(status=PartnerStatus.REJECTED.value, bps=2500, promo_percent=50)
    info = calculate_user_price(user, 10000, 30, 'period')
    assert info.final_price == 5000
    assert info.base_price == 10000


def test_no_custom_pricing_seam():
    assert importlib.util.find_spec('app.custom.pricing') is None
