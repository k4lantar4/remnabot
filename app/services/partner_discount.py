"""Deprecated partner discount helpers — redirect to DB wholesale BPS."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Literal

from app.services.pricing_engine import PricingEngine


if TYPE_CHECKING:
    from app.database.models import User

PartnerDiscountScope = Literal['purchase', 'traffic', 'extension']


def get_partner_discount_percent(user: User | None, scope: PartnerDiscountScope) -> int:
    """Deprecated: use ``PricingEngine.get_wholesale_discount_bps`` (scope ignored)."""
    warnings.warn(
        'partner_discount.get_partner_discount_percent is deprecated; use wholesale_discount_bps',
        DeprecationWarning,
        stacklevel=2,
    )
    del scope
    return PricingEngine.get_wholesale_discount_bps(user) // 100


def apply_if_partner(
    amount: int,
    user: User | None,
    scope: PartnerDiscountScope,
) -> tuple[int, int]:
    """Deprecated: use ``PricingEngine.apply_wholesale_discount`` (scope ignored)."""
    warnings.warn(
        'partner_discount.apply_if_partner is deprecated; use PricingEngine.apply_wholesale_discount',
        DeprecationWarning,
        stacklevel=2,
    )
    del scope
    return PricingEngine.apply_wholesale_discount(amount, user)
