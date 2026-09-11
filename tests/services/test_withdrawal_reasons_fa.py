"""Withdrawal refusal reasons reach the user in their language (F-009).

``can_request_withdrawal`` returns a reason the bot (``referral.py``) and the cabinet withdrawal
screen show as-is. The below-minimum reason was already localized; «feature disabled», «next
request in N days» and «you already have a pending request» were hard-coded Russian.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings, settings
from app.database.models import ReferralEarning, WithdrawalRequest, WithdrawalRequestStatus
from app.services.referral_withdrawal_service import ReferralWithdrawalService
from tests.fixtures.sqlite_memory import memory_session
from tests.services.test_withdrawal_amounts_toman import (  # noqa: F401 - _withdrawals_on is a fixture
    AVAILABLE,
    TABLES,
    _user_row,
    _withdrawals_on,
)


CYRILLIC = re.compile('[А-Яа-яЁё]')
pytestmark = pytest.mark.asyncio


async def _seed(db, *, last_request: WithdrawalRequest | None = None) -> None:
    db.add(_user_row())
    db.add(_user_row(user_id=3, balance=0))
    db.add(ReferralEarning(user_id=1, referral_id=3, amount_kopeks=AVAILABLE, reason='referral_commission_topup'))
    if last_request is not None:
        db.add(last_request)
    await db.commit()


async def test_disabled_reason_is_persian(monkeypatch):
    monkeypatch.setattr(Settings, 'is_referral_withdrawal_enabled', lambda self: False)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db)
        ok, reason, _stats = await ReferralWithdrawalService().can_request_withdrawal(db, 1)

    assert ok is False
    assert reason.strip()
    assert not CYRILLIC.search(reason), reason


async def test_cooldown_reason_is_persian_and_keeps_the_days(monkeypatch, _withdrawals_on):
    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_COOLDOWN_DAYS', 7)
    last = WithdrawalRequest(
        id=1,
        user_id=1,
        amount_kopeks=10_000,
        payment_details='card',
        status=WithdrawalRequestStatus.APPROVED.value,
        created_at=datetime.now(UTC) - timedelta(days=1, hours=1),
    )
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, last_request=last)
        ok, reason, _stats = await ReferralWithdrawalService().can_request_withdrawal(db, 1)

    assert ok is False
    assert not CYRILLIC.search(reason), reason
    assert '6' in reason, reason  # 7-day cooldown, requested ~1 day ago: 6 days left


async def test_pending_request_reason_is_persian(monkeypatch, _withdrawals_on):
    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_TEST_MODE', True)  # skip the cooldown check
    last = WithdrawalRequest(
        id=1,
        user_id=1,
        amount_kopeks=10_000,
        payment_details='card',
        status=WithdrawalRequestStatus.PENDING.value,
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db, last_request=last)
        ok, reason, _stats = await ReferralWithdrawalService().can_request_withdrawal(db, 1)

    assert ok is False
    assert reason.strip()
    assert not CYRILLIC.search(reason), reason
