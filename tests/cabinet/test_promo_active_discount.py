"""Plan 2026-09-11 Task 3: the cabinet must not stack a promo offer onto a partner's price.

The cabinet applies the active offer itself (``combinePromoDiscount``) from
``GET /cabinet/promo/active-discount``. The server never applies an offer to an approved
wholesale partner, so the endpoint reports it inactive for them; the stored offer is untouched.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.cabinet.routes.promo import get_active_discount
from app.database.models import PartnerStatus


def _user(*, status: str = PartnerStatus.NONE.value, bps: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        partner_status=status,
        wholesale_discount_bps=bps,
        promo_offer_discount_percent=20,
        promo_offer_discount_expires_at=datetime.now(UTC) + timedelta(days=1),
        promo_offer_discount_source='test',
    )


@pytest.mark.asyncio
async def test_approved_wholesale_partner_sees_no_active_offer():
    user = _user(status=PartnerStatus.APPROVED.value, bps=3000)
    info = await get_active_discount(user=user)
    assert info.is_active is False
    assert info.discount_percent == 0
    assert user.promo_offer_discount_percent == 20, 'the stored offer is left alone'


@pytest.mark.asyncio
async def test_b2c_user_sees_the_offer():
    info = await get_active_discount(user=_user())
    assert (info.is_active, info.discount_percent) == (True, 20)


@pytest.mark.asyncio
async def test_pending_partner_sees_the_offer():
    info = await get_active_discount(user=_user(status=PartnerStatus.PENDING.value, bps=3000))
    assert (info.is_active, info.discount_percent) == (True, 20)
