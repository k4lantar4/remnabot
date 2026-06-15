"""Tests for deprecated partner_discount redirect to wholesale BPS."""

from unittest.mock import MagicMock

import pytest

from app.database.models import PartnerStatus
from app.services.partner_discount import apply_if_partner, get_partner_discount_percent


def _partner_user(*, bps: int = 2500) -> MagicMock:
    user = MagicMock()
    user.partner_status = PartnerStatus.APPROVED.value
    user.is_partner = True
    user.wholesale_discount_bps = bps
    return user


class TestPartnerDiscountDeprecation:
    def test_get_partner_discount_percent_from_bps(self):
        with pytest.warns(DeprecationWarning):
            assert get_partner_discount_percent(_partner_user(bps=2500), 'purchase') == 25

    def test_get_partner_discount_percent_non_partner(self):
        with pytest.warns(DeprecationWarning):
            assert get_partner_discount_percent(MagicMock(is_partner=False), 'traffic') == 0

    def test_apply_if_partner_uses_wholesale(self):
        with pytest.warns(DeprecationWarning):
            final, discount = apply_if_partner(10000, _partner_user(bps=2500), 'extension')
        assert final == 7500
        assert discount == 2500
