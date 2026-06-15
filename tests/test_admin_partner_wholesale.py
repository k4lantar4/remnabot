"""Tests for admin partner wholesale schema validation."""

import pytest
from pydantic import ValidationError

from app.cabinet.schemas.partners import AdminUpdateWholesaleRequest


class TestAdminUpdateWholesaleRequest:
    def test_accepts_valid_bps(self):
        req = AdminUpdateWholesaleRequest(wholesale_discount_bps=2500)
        assert req.wholesale_discount_bps == 2500

    def test_accepts_zero(self):
        req = AdminUpdateWholesaleRequest(wholesale_discount_bps=0)
        assert req.wholesale_discount_bps == 0

    def test_accepts_max_bps(self):
        req = AdminUpdateWholesaleRequest(wholesale_discount_bps=10000)
        assert req.wholesale_discount_bps == 10000

    def test_rejects_negative(self):
        with pytest.raises(ValidationError):
            AdminUpdateWholesaleRequest(wholesale_discount_bps=-1)

    def test_rejects_over_max(self):
        with pytest.raises(ValidationError):
            AdminUpdateWholesaleRequest(wholesale_discount_bps=10001)

    def test_rejects_float(self):
        with pytest.raises(ValidationError):
            AdminUpdateWholesaleRequest(wholesale_discount_bps=25.5)  # type: ignore[arg-type]
