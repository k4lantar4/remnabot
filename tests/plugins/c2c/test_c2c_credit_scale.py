"""C2C approve credits receipt amount at balance Toman scale (1:1)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.database.models import C2cReceiptStatus, PaymentMethod, TransactionType
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.service import C2cPaymentService


@pytest.mark.asyncio
async def test_approve_credits_full_receipt_amount_without_div100(monkeypatch):
    """10M Toman receipt must credit 10M, not catalog_price_in_toman (100k)."""
    receipt_amount = 10_000_000
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    receipt = SimpleNamespace(
        id=5,
        user_id=1,
        amount_kopeks=receipt_amount,
        status=C2cReceiptStatus.PENDING.value,
        transaction_id=None,
        reviewed_by_telegram_id=None,
        processed_at=None,
        updated_at=None,
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
    success, message, _ = await service.approve_receipt(db, 5, 777)

    assert success is True
    assert message == 'Approved'

    add_balance.assert_awaited_once()
    assert add_balance.await_args.args[2] == receipt_amount

    create_tx.assert_awaited_once()
    assert create_tx.await_args.kwargs['amount_kopeks'] == receipt_amount
    assert create_tx.await_args.kwargs['type'] == TransactionType.DEPOSIT
    assert create_tx.await_args.kwargs['payment_method'] == PaymentMethod.C2C

    finalize.assert_awaited_once()
    assert finalize.await_args.args[3] == receipt_amount
