"""process_referral_purchase credits its commission in Toman (F-007 part b).

The function has no callers today (upstream keeps it, so do we). It used to take a catalog purchase
amount (Toman x 100) while crediting the commission 1:1 into the Toman balance, so the percentage
had to be taken after a conversion. Since revision 0115 both sides are Toman: 10% of a
1,000,000-Toman purchase is 100,000 Toman.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.services import referral_service


PURCHASE_TOMAN = 1_000_000
COMMISSION_TOMAN = 100_000  # 10%


@pytest.mark.asyncio
async def test_commission_is_a_percentage_of_the_toman_purchase(monkeypatch):
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

    assert await referral_service.process_referral_purchase(None, 4, PURCHASE_TOMAN, bot=object()) is True

    assert credit.await_args.args[2] == COMMISSION_TOMAN
    assert earning.await_args.kwargs['amount_kopeks'] == COMMISSION_TOMAN  # ReferralEarning is Toman
    text = notify.await_args.args[2]
    assert settings.format_balance(PURCHASE_TOMAN) in text
    assert settings.format_balance(COMMISSION_TOMAN) in text
    assert notify.await_args.kwargs['bonus_kopeks'] == COMMISSION_TOMAN
