"""Tests for C2C custom approve amount and structured reject."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.database.models import C2cReceiptStatus, PaymentMethod, TransactionType
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.service import C2cPaymentService


@pytest.mark.asyncio
async def test_approve_with_custom_amount_credits_requested_value(monkeypatch):
    receipt_amount = 1_000_000
    custom_credit = 800_000
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    receipt = SimpleNamespace(
        id=9,
        user_id=1,
        amount_kopeks=receipt_amount,
        status=C2cReceiptStatus.PENDING.value,
        transaction_id=None,
        reviewed_by_telegram_id=None,
        processed_at=None,
        updated_at=None,
        approved_amount_kopeks=None,
    )
    user = SimpleNamespace(
        id=1,
        telegram_id=123,
        balance_kopeks=0,
        has_made_first_topup=False,
        referred_by_id=None,
    )
    created_tx = SimpleNamespace(id=50)

    monkeypatch.setattr(c2c_crud, 'get_c2c_receipt_for_update', AsyncMock(return_value=receipt))
    monkeypatch.setattr(
        'app.plugins.c2c.service.get_transaction_by_external_id',
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr('app.plugins.c2c.service.get_user_by_id', AsyncMock(return_value=user))
    monkeypatch.setattr('app.plugins.c2c.service.lock_user_for_update', AsyncMock(return_value=user))
    add_balance = AsyncMock(return_value=True)
    monkeypatch.setattr('app.plugins.c2c.service.add_user_balance', add_balance)
    create_tx = AsyncMock(return_value=created_tx)
    monkeypatch.setattr('app.plugins.c2c.service.create_transaction', create_tx)
    finalize = AsyncMock()
    monkeypatch.setattr(C2cPaymentService, 'finalize_approved_topup', finalize)
    monkeypatch.setattr('app.plugins.c2c.service.clear_user_c2c_fsm_state', AsyncMock())

    service = C2cPaymentService(bot=None)
    success, message, _ = await service.approve_receipt(
        db,
        9,
        777,
        credited_amount_kopeks=custom_credit,
    )

    assert success is True
    assert message == 'Approved'
    assert receipt.approved_amount_kopeks == custom_credit
    add_balance.assert_awaited_once()
    assert add_balance.await_args.args[2] == custom_credit
    create_tx.assert_awaited_once()
    assert create_tx.await_args.kwargs['amount_kopeks'] == custom_credit


@pytest.mark.asyncio
async def test_reject_silent_skips_user_notification(monkeypatch):
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    receipt = SimpleNamespace(
        id=3,
        user_id=2,
        amount_kopeks=50000,
        status=C2cReceiptStatus.PENDING.value,
        reviewed_by_telegram_id=None,
        rejection_reason=None,
        rejection_reason_key=None,
        processed_at=None,
        updated_at=None,
    )
    user = SimpleNamespace(id=2, telegram_id=999, language='fa')

    monkeypatch.setattr(c2c_crud, 'get_c2c_receipt_for_update', AsyncMock(return_value=receipt))
    monkeypatch.setattr('app.plugins.c2c.service.get_user_by_id', AsyncMock(return_value=user))
    monkeypatch.setattr('app.plugins.c2c.service.clear_user_c2c_fsm_state', AsyncMock())

    bot = AsyncMock()
    service = C2cPaymentService(bot=bot)
    success, message, updated = await service.reject_receipt(
        db,
        3,
        111,
        reason_key='silent',
    )

    assert success is True
    assert message == 'Rejected'
    assert updated is receipt
    assert receipt.rejection_reason_key == 'silent'
    bot.send_message.assert_not_awaited()
