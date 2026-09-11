"""process_referral_purchase credits its commission in Toman (F-007 part b).

The function has no callers today (upstream keeps it, so do we), but its base is a catalog
purchase amount (Toman x 100) while the commission lands 1:1 in the Toman balance. 10% of a
1,000,000-kopek (10,000-Toman) purchase is 1,000 Toman, not 100,000.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.services import referral_service


PURCHASE_KOPEKS = 1_000_000  # catalog: 10,000 Toman
COMMISSION_TOMAN = 1_000  # 10%


@pytest.mark.asyncio
async def test_commission_on_a_catalog_purchase_is_credited_in_toman(monkeypatch):
    referee = SimpleNamespace(id=4, referred_by_id=3, full_name='Sara', has_had_paid_subscription=True)
    referrer = SimpleNamespace(id=3, telegram_id=1003, email=None, language='fa')
    credit = AsyncMock(return_value=True)
    earning = AsyncMock()
    notify = AsyncMock()

    async def fake_get_user(_db, uid):
        return {3: referrer, 4: referee}[uid]

    monkeypatch.setattr(referral_service, 'get_user_by_id', fake_get_user)
    monkeypatch.setattr(referral_service, 'get_effective_referral_commission_percent', lambda _user: 10)
    monkeypatch.setattr(referral_service, 'add_user_balance', credit)
    monkeypatch.setattr(referral_service, 'create_referral_earning', earning)
    monkeypatch.setattr(referral_service, 'get_user_campaign_id', AsyncMock(return_value=None))
    monkeypatch.setattr(referral_service, 'send_referral_notification', notify)

    assert await referral_service.process_referral_purchase(None, 4, PURCHASE_KOPEKS, bot=object()) is True

    assert credit.await_args.args[2] == COMMISSION_TOMAN
    assert earning.await_args.kwargs['amount_kopeks'] == COMMISSION_TOMAN  # ReferralEarning is Toman
    text = notify.await_args.args[2]
    assert settings.format_price(PURCHASE_KOPEKS) in text  # the purchase is a catalog price
    assert settings.format_balance(COMMISSION_TOMAN) in text  # the commission is balance Toman
    assert notify.await_args.kwargs['bonus_kopeks'] == COMMISSION_TOMAN
