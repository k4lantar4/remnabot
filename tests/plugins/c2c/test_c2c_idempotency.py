"""C2C idempotency and duplicate-pending guards."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database.models import C2cReceiptStatus, PaymentMethod, TransactionType
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.service import C2cPaymentService, c2c_external_id


@pytest.mark.asyncio
async def test_double_approve_uses_existing_transaction(monkeypatch):
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    receipt = SimpleNamespace(
        id=7,
        user_id=42,
        amount_kopeks=50000,
        status=C2cReceiptStatus.PENDING.value,
        transaction_id=None,
    )
    existing_tx = SimpleNamespace(id=999)

    monkeypatch.setattr(c2c_crud, 'get_c2c_receipt_for_update', AsyncMock(return_value=receipt))
    monkeypatch.setattr(
        'app.plugins.c2c.service.get_transaction_by_external_id',
        AsyncMock(return_value=existing_tx),
    )
    add_balance = AsyncMock()
    monkeypatch.setattr('app.plugins.c2c.service.add_user_balance', add_balance)
    create_tx = AsyncMock()
    monkeypatch.setattr('app.plugins.c2c.service.create_transaction', create_tx)
    monkeypatch.setattr('app.plugins.c2c.service.clear_user_c2c_fsm_state', AsyncMock())

    service = C2cPaymentService(bot=None)
    success, message, updated = await service.approve_receipt(db, 7, 111)

    assert success is True
    assert message == 'Already credited'
    assert updated is receipt
    assert receipt.status == C2cReceiptStatus.APPROVED.value
    assert receipt.transaction_id == 999
    add_balance.assert_not_called()
    create_tx.assert_not_called()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_duplicate_pending_receipt_guard():
    db = AsyncMock()
    pending = SimpleNamespace(id=3)

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = pending
    db.execute = AsyncMock(return_value=execute_result)

    result = await c2c_crud.get_pending_receipt_for_user(db, user_id=10)
    assert result is pending
    assert await c2c_crud.user_has_pending_receipt(db, user_id=10) is True


@pytest.mark.asyncio
async def test_external_id_collision_blocks_second_credit(monkeypatch):
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    receipt = SimpleNamespace(
        id=5,
        user_id=1,
        amount_kopeks=10000,
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
    monkeypatch.setattr('app.plugins.c2c.service.add_user_balance', AsyncMock(return_value=True))
    create_tx = AsyncMock(return_value=created_tx)
    monkeypatch.setattr('app.plugins.c2c.service.create_transaction', create_tx)
    finalize = AsyncMock()
    monkeypatch.setattr(C2cPaymentService, 'finalize_approved_topup', finalize)
    monkeypatch.setattr('app.plugins.c2c.service.clear_user_c2c_fsm_state', AsyncMock())

    bot = AsyncMock()
    bot.id = 1
    service = C2cPaymentService(bot=bot)
    success, message, _ = await service.approve_receipt(db, 5, 777)

    assert success is True
    assert message == 'Approved'
    assert c2c_external_id(5) == 'c2c:5'

    create_tx.assert_awaited_once()
    kwargs = create_tx.await_args.kwargs
    assert kwargs['external_id'] == 'c2c:5'
    assert kwargs['payment_method'] == PaymentMethod.C2C
    assert kwargs['type'] == TransactionType.DEPOSIT
    finalize.assert_awaited_once()
