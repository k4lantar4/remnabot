from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.database.models import PartnerStatus
from app.services.partner_application_service import PartnerApplicationService


def _make_application(*, application_id: int = 1, user_id: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        id=application_id,
        user_id=user_id,
        status=PartnerStatus.PENDING.value,
        approved_commission_percent=None,
        admin_comment=None,
        processed_by=None,
        processed_at=None,
    )


def _make_user(*, user_id: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        telegram_id=123456,
        referral_code='ref123',
        partner_status=PartnerStatus.PENDING.value,
        business_role='customer',
        referral_commission_percent=20,
        wholesale_discount_bps=0,
    )


@pytest.mark.asyncio
async def test_approve_application_sets_wholesale_not_referral_commission() -> None:
    service = PartnerApplicationService()
    application = _make_application()
    user = _make_user()

    app_result = SimpleNamespace(scalar_one_or_none=lambda: application)
    user_result = SimpleNamespace(scalar_one_or_none=lambda: user)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[app_result, user_result])
    db.commit = AsyncMock()

    with (
        patch(
            'app.database.crud.promo_group.get_promo_group_by_name',
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            'app.database.crud.user_promo_group.add_user_to_promo_group',
            new_callable=AsyncMock,
        ),
    ):
        success, error = await service.approve_application(
            db,
            application_id=1,
            admin_id=99,
            commission_percent=30,
        )

    assert success is True
    assert error == ''
    assert user.wholesale_discount_bps == 3000
    assert user.referral_commission_percent is None
    assert user.partner_status == PartnerStatus.APPROVED.value
    assert user.business_role == 'partner'
    assert application.approved_commission_percent == 30
    db.commit.assert_awaited_once()
