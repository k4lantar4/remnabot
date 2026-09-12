"""Cabinet adapter for card-to-card top-ups: the bot's C2C rules, driven from HTTP.

The adapter speaks Toman 1:1 (the database scale since Phase C); the wire x100 is the route's job.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.models import C2cReceiptStatus
from app.plugins.c2c import cabinet, crud as real_crud
from app.plugins.c2c.constants import C2C_RECEIPT_TYPE_PHOTO, C2C_RECEIPT_TYPE_TEXT


CARD = {'label': 'Melli', 'number': '6037000000000001', 'holder': 'Ali'}


def _user(**overrides):
    data = {'id': 42, 'telegram_id': 111, 'language': 'fa'}
    data.update(overrides)
    return SimpleNamespace(**data)


def _receipt(**overrides):
    now = datetime.now(UTC)
    data = {
        'id': 7,
        'user_id': 42,
        'status': C2cReceiptStatus.PENDING.value,
        'amount_kopeks': 20_000,
        'receipt_type': None,
        'receipt_file_id': None,
        'receipt_text': None,
        'card_index': 3,
        'card_label': 'Old',
        'created_at': now,
        'updated_at': now,
        'expires_at': None,
        'processed_at': None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def crud(monkeypatch):
    fake = SimpleNamespace(
        expire_stale_c2c_receipts=AsyncMock(return_value=0),
        # Unlocked read: only `current` may use it. Anything that changes a receipt locks the row.
        get_pending_receipt_for_user=AsyncMock(return_value=None),
        get_pending_receipt_for_user_for_update=AsyncMock(return_value=None),
        create_pending_receipt=AsyncMock(
            side_effect=lambda db, **kw: _receipt(
                id=9,
                amount_kopeks=kw['amount_kopeks'],
                card_index=kw['card_index'],
                card_label=kw['card_label'],
            )
        ),
        get_c2c_receipt_by_id=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(cabinet, 'c2c_crud', fake)
    monkeypatch.setattr(cabinet, 'get_next_card', AsyncMock(return_value=(CARD, 0)))
    return fake


@pytest.fixture
def service(monkeypatch):
    svc = MagicMock()
    svc.submit_receipt = AsyncMock(return_value=(True, 'OK', 555))
    monkeypatch.setattr(cabinet, 'C2cPaymentService', lambda bot: svc)

    @asynccontextmanager
    async def _fake_bot():
        yield MagicMock()

    monkeypatch.setattr(cabinet, 'create_bot', _fake_bot)
    cart = MagicMock()
    cart.refresh_topup_intent = AsyncMock()
    monkeypatch.setattr(cabinet, 'user_cart_service', cart)
    return svc


# ---- start ----------------------------------------------------------------


async def test_start_creates_a_pending_receipt_in_toman(crud):
    db = _db()

    receipt = await cabinet.start_cabinet_receipt(db, _user(), 100_000)

    crud.create_pending_receipt.assert_awaited_once()
    kwargs = crud.create_pending_receipt.await_args.kwargs
    assert kwargs == {'user_id': 42, 'amount_kopeks': 100_000, 'card_index': 0, 'card_label': 'Melli'}
    assert receipt.amount_kopeks == 100_000
    db.commit.assert_awaited()


async def test_start_reuses_a_receipt_less_pending_instead_of_inserting(crud):
    pending = _receipt()
    crud.get_pending_receipt_for_user_for_update.return_value = pending

    receipt = await cabinet.start_cabinet_receipt(_db(), _user(), 150_000)

    assert receipt is pending
    assert pending.amount_kopeks == 150_000
    assert pending.card_index == 0
    assert pending.card_label == 'Melli'
    assert pending.expires_at is not None
    crud.create_pending_receipt.assert_not_awaited()


async def test_start_refuses_while_a_submitted_receipt_is_pending(crud):
    pending = _receipt(receipt_type=C2C_RECEIPT_TYPE_PHOTO)
    crud.get_pending_receipt_for_user_for_update.return_value = pending

    with pytest.raises(cabinet.C2cCabinetError) as exc:
        await cabinet.start_cabinet_receipt(_db(), _user(), 150_000)

    assert exc.value.code == cabinet.ALREADY_SUBMITTED
    assert exc.value.receipt is pending
    assert pending.amount_kopeks == 20_000
    crud.create_pending_receipt.assert_not_awaited()


async def test_start_without_cards_is_unavailable(crud):
    cabinet.get_next_card.side_effect = ValueError('C2C cards are not configured')

    with pytest.raises(cabinet.C2cCabinetError) as exc:
        await cabinet.start_cabinet_receipt(_db(), _user(), 150_000)

    assert exc.value.code == cabinet.UNAVAILABLE


async def test_start_reprices_the_receipt_a_parallel_session_just_inserted(crud):
    # Two first sessions at once: both see no pending row, the second insert hits the
    # one-pending-per-user unique index. It must re-price the winner's row, not answer 500.
    winner = _receipt(id=11)
    crud.create_pending_receipt.side_effect = IntegrityError('INSERT', {}, Exception('uq_c2c_receipts_user_pending'))
    crud.get_pending_receipt_for_user_for_update.side_effect = [None, winner]
    db = _db()

    receipt = await cabinet.start_cabinet_receipt(db, _user(), 150_000)

    db.rollback.assert_awaited_once()
    assert receipt is winner
    assert winner.amount_kopeks == 150_000


# ---- attach ---------------------------------------------------------------


async def test_attach_image_with_note_submits_one_photo_receipt(crud, service):
    pending = _receipt()
    crud.get_pending_receipt_for_user_for_update.return_value = pending
    db = _db()
    user = _user()

    receipt = await cabinet.attach_cabinet_receipt(
        db, user, 7, media_file_id='AgACfile', media_type='photo', text='  paid 10:30  '
    )

    service.submit_receipt.assert_awaited_once()
    kwargs = service.submit_receipt.await_args.kwargs
    assert kwargs['receipt'] is pending
    assert kwargs['receipt_type'] == C2C_RECEIPT_TYPE_PHOTO
    assert kwargs['receipt_file_id'] == 'AgACfile'
    assert kwargs['receipt_text'] == 'paid 10:30'
    assert kwargs['user_receipt_message_id'] is None
    assert kwargs['user'] is user
    assert receipt is pending
    db.commit.assert_awaited()


async def test_attach_reads_the_pending_row_under_lock(crud, service):
    # Without the lock a parallel /c2c/session could re-price the receipt while the admin
    # message is being sent, and the admin would approve an amount they never saw.
    crud.get_pending_receipt_for_user_for_update.return_value = _receipt()

    await cabinet.attach_cabinet_receipt(_db(), _user(), 7, media_file_id='f', media_type='photo', text=None)

    crud.get_pending_receipt_for_user_for_update.assert_awaited_once()
    crud.get_pending_receipt_for_user.assert_not_awaited()


async def test_attach_text_only_submits_a_text_receipt(crud, service):
    crud.get_pending_receipt_for_user_for_update.return_value = _receipt()

    await cabinet.attach_cabinet_receipt(_db(), _user(), 7, media_file_id=None, media_type=None, text='ref 123456')

    kwargs = service.submit_receipt.await_args.kwargs
    assert kwargs['receipt_type'] == C2C_RECEIPT_TYPE_TEXT
    assert kwargs['receipt_file_id'] is None
    assert kwargs['receipt_text'] == 'ref 123456'


async def test_attach_empty_submission_is_rejected(crud, service):
    crud.get_pending_receipt_for_user_for_update.return_value = _receipt()

    with pytest.raises(cabinet.C2cCabinetError) as exc:
        await cabinet.attach_cabinet_receipt(_db(), _user(), 7, media_file_id=None, media_type=None, text='   ')

    assert exc.value.code == cabinet.EMPTY
    service.submit_receipt.assert_not_awaited()


async def test_attach_to_someone_elses_or_missing_receipt_is_not_found(crud, service):
    crud.get_pending_receipt_for_user_for_update.return_value = _receipt(id=8)

    with pytest.raises(cabinet.C2cCabinetError) as exc:
        await cabinet.attach_cabinet_receipt(_db(), _user(), 7, media_file_id='f', media_type='photo', text=None)

    assert exc.value.code == cabinet.NOT_FOUND
    service.submit_receipt.assert_not_awaited()


async def test_attach_twice_is_already_submitted(crud, service):
    crud.get_pending_receipt_for_user_for_update.return_value = _receipt(receipt_type=C2C_RECEIPT_TYPE_PHOTO)

    with pytest.raises(cabinet.C2cCabinetError) as exc:
        await cabinet.attach_cabinet_receipt(_db(), _user(), 7, media_file_id='f', media_type='photo', text=None)

    assert exc.value.code == cabinet.ALREADY_SUBMITTED
    service.submit_receipt.assert_not_awaited()


async def test_attach_when_admin_chat_fails_keeps_the_receipt_pending(crud, service):
    pending = _receipt()
    crud.get_pending_receipt_for_user_for_update.return_value = pending
    service.submit_receipt.return_value = (False, 'Failed to notify administrators', None)

    with pytest.raises(cabinet.C2cCabinetError) as exc:
        await cabinet.attach_cabinet_receipt(_db(), _user(), 7, media_file_id='f', media_type='photo', text=None)

    assert exc.value.code == cabinet.ADMIN_UNREACHABLE
    assert pending.status == C2cReceiptStatus.PENDING.value
    assert pending.receipt_type is None


# ---- current / cancel -----------------------------------------------------


async def test_current_returns_the_pending_receipt_or_none(crud):
    assert await cabinet.current_cabinet_receipt(_db(), _user()) is None

    pending = _receipt()
    crud.get_pending_receipt_for_user.return_value = pending
    assert await cabinet.current_cabinet_receipt(_db(), _user()) is pending


async def test_current_by_id_follows_a_processed_receipt_of_the_same_user_only(crud):
    approved = _receipt(status=C2cReceiptStatus.APPROVED.value, receipt_type=C2C_RECEIPT_TYPE_PHOTO)
    crud.get_c2c_receipt_by_id.return_value = approved
    assert await cabinet.current_cabinet_receipt(_db(), _user(), receipt_id=7) is approved

    crud.get_c2c_receipt_by_id.return_value = _receipt(user_id=99)
    assert await cabinet.current_cabinet_receipt(_db(), _user(), receipt_id=7) is None


async def test_cancel_closes_a_receipt_less_pending(crud):
    pending = _receipt()
    crud.get_pending_receipt_for_user_for_update.return_value = pending
    db = _db()

    receipt = await cabinet.cancel_cabinet_receipt(db, _user(), 7)

    assert receipt is pending
    assert pending.status == C2cReceiptStatus.CANCELLED.value
    assert pending.processed_at is not None
    db.commit.assert_awaited()


async def test_cancel_refuses_a_submitted_receipt(crud):
    pending = _receipt(receipt_type=C2C_RECEIPT_TYPE_PHOTO)
    crud.get_pending_receipt_for_user_for_update.return_value = pending

    with pytest.raises(cabinet.C2cCabinetError) as exc:
        await cabinet.cancel_cabinet_receipt(_db(), _user(), 7)

    assert exc.value.code == cabinet.ALREADY_SUBMITTED
    assert pending.status == C2cReceiptStatus.PENDING.value


# ---- crud -----------------------------------------------------------------


async def test_locked_pending_lookup_selects_for_update_and_refreshes_the_row():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    assert await real_crud.get_pending_receipt_for_user_for_update(db, 42) is None

    statement = db.execute.await_args.args[0]
    assert statement._for_update_arg is not None
    # A row already in the session's identity map must be re-read, or the lock guards stale data.
    assert statement.get_execution_options().get('populate_existing') is True
