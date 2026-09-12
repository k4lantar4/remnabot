"""Cabinet admin C2C receipt review — approve and reject through the real ``C2cPaymentService``.

A real (SQLite) session backs the credit and the ledger row; Telegram is a fake bot, and the post-credit
side effects (referrals, cart, notifications) are stubbed since they belong to the service, not here.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.cabinet.dependencies import get_cabinet_db
from app.cabinet.routes import admin_c2c_receipts as route
from app.database.models import (
    C2cReceipt,
    C2cReceiptStatus,
    PromoGroup,
    Subscription,
    Tariff,
    Transaction,
    User,
    UserPromoGroup,
)
from app.plugins.c2c import service as c2c_service
from tests.fixtures.sqlite_memory import memory_session


# get_user_by_id eager-loads subscriptions (+ tariff) and promo groups.
TABLES = (
    PromoGroup.__table__,
    User.__table__,
    UserPromoGroup.__table__,
    Tariff.__table__,
    Subscription.__table__,
    Transaction.__table__,
    C2cReceipt.__table__,
)
NOW = datetime.now(UTC).replace(microsecond=0)
ADMIN = SimpleNamespace(id=1, telegram_id=777, username='boss', language='fa')


class FakeBot:
    def __init__(self) -> None:
        self.id = 42
        self.edit_message_text = AsyncMock()
        self.edit_message_caption = AsyncMock()
        self.send_message = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False


async def _seed(db) -> None:
    db.add(User(id=1, telegram_id=777, username='boss', first_name='Owner', language='fa'))
    db.add(User(id=10, telegram_id=1001, username='alice', first_name='Ali', language='fa', balance_kopeks=40_000))
    db.add(
        C2cReceipt(
            id=1,
            user_id=10,
            amount_kopeks=250_000,
            status=C2cReceiptStatus.PENDING.value,
            receipt_type='photo',
            receipt_file_id='AgACAgQAAxkBAAIBc2Mfile_id_1234567890',
            card_index=0,
            card_label='Melli',
            admin_chat_id=-100123,
            admin_message_id=55,
            created_at=NOW - timedelta(hours=1),
            updated_at=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=23),
        )
    )
    await db.commit()


@contextlib.asynccontextmanager
async def _client(monkeypatch):
    bot = FakeBot()
    monkeypatch.setattr(route, 'create_bot', lambda: bot)
    monkeypatch.setattr(route, 'resolved_receipt_message', AsyncMock(return_value=('<b>resolved</b>', None)))
    monkeypatch.setattr(route, 'get_card_by_index', lambda index: None)
    monkeypatch.setattr(c2c_service.C2cPaymentService, 'finalize_approved_topup', AsyncMock())
    monkeypatch.setattr(c2c_service, 'clear_user_c2c_fsm_state', AsyncMock())
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db)
        app = FastAPI()
        app.include_router(route.router, prefix='/cabinet')
        app.dependency_overrides[get_cabinet_db] = lambda: db
        for candidate in route.router.routes:
            for dependant in candidate.dependant.dependencies:
                call = dependant.call
                if getattr(call, '__name__', '') == 'dependency' and getattr(call, '__module__', '').endswith(
                    'cabinet.dependencies'
                ):
                    app.dependency_overrides[call] = lambda: ADMIN
        with TestClient(app) as http:
            yield http, db, bot


async def _deposits(db) -> list[Transaction]:
    result = await db.execute(select(Transaction).where(Transaction.external_id == 'c2c:1'))
    return list(result.scalars().all())


async def _balance(db) -> int:
    result = await db.execute(select(User.balance_kopeks).where(User.id == 10))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_approve_credits_the_requested_amount_and_names_the_reviewer(monkeypatch):
    async with _client(monkeypatch) as (http, db, bot):
        response = http.post('/cabinet/admin/c2c-receipts/1/approve', json={})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body['status'] == 'approved'
        assert body['approved_amount_toman'] == 250_000
        assert body['reviewer'] == {'user_id': 1, 'telegram_id': 777, 'label': 'boss', 'via': 'cabinet'}
        assert body['user_balance_toman'] == 290_000
        assert await _balance(db) == 290_000
        deposits = await _deposits(db)
        assert [(d.amount_kopeks, d.type) for d in deposits] == [(250_000, 'deposit')]
        # The Telegram group post is rewritten to its resolved form.
        bot.edit_message_text.assert_awaited_once()
        assert bot.edit_message_text.await_args.kwargs['message_id'] == 55


@pytest.mark.asyncio
async def test_approve_with_a_different_amount_converts_from_the_wire_scale(monkeypatch):
    async with _client(monkeypatch) as (http, db, _bot):
        response = http.post('/cabinet/admin/c2c-receipts/1/approve', json={'amount_kopeks': 20_000_000})

        assert response.status_code == 200, response.text
        assert response.json()['approved_amount_toman'] == 200_000
        assert await _balance(db) == 240_000


@pytest.mark.asyncio
async def test_approving_twice_is_a_conflict_and_credits_once(monkeypatch):
    async with _client(monkeypatch) as (http, db, _bot):
        first = http.post('/cabinet/admin/c2c-receipts/1/approve', json={})
        second = http.post('/cabinet/admin/c2c-receipts/1/approve', json={})

        assert first.status_code == 200, first.text
        assert second.status_code == 409, second.text
        assert second.json()['detail'] == 'این رسید قبلاً بررسی شده است.'
        assert await _balance(db) == 290_000
        assert len(await _deposits(db)) == 1


@pytest.mark.asyncio
async def test_approve_amount_outside_the_limits_is_refused(monkeypatch):
    async with _client(monkeypatch) as (http, db, _bot):
        response = http.post('/cabinet/admin/c2c-receipts/1/approve', json={'amount_kopeks': 100})

        assert response.status_code == 400, response.text
        assert await _balance(db) == 40_000
        receipt = await db.get(C2cReceipt, 1)
        assert receipt.status == 'pending'


@pytest.mark.asyncio
async def test_unknown_receipt_is_404(monkeypatch):
    async with _client(monkeypatch) as (http, _db, _bot):
        assert http.post('/cabinet/admin/c2c-receipts/999/approve', json={}).status_code == 404
        assert http.post('/cabinet/admin/c2c-receipts/999/reject', json={'reason_key': 'unclear'}).status_code == 404


@pytest.mark.asyncio
async def test_reject_stores_the_reason_and_tells_the_user(monkeypatch):
    async with _client(monkeypatch) as (http, db, bot):
        response = http.post(
            '/cabinet/admin/c2c-receipts/1/reject',
            json={'reason_key': 'amt_mismatch', 'comment': '  paid 200k only  '},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body['status'] == 'rejected'
        assert body['rejection_reason_key'] == 'amt_mismatch'
        assert body['rejection_reason'] == 'paid 200k only'
        assert body['reviewer']['via'] == 'cabinet'
        assert await _balance(db) == 40_000
        assert await _deposits(db) == []
        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.args[0] == 1001
        bot.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_silent_reject_sends_the_user_nothing(monkeypatch):
    async with _client(monkeypatch) as (http, _db, bot):
        response = http.post('/cabinet/admin/c2c-receipts/1/reject', json={'reason_key': 'silent'})

        assert response.status_code == 200, response.text
        bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_reason_is_400(monkeypatch):
    async with _client(monkeypatch) as (http, db, _bot):
        response = http.post('/cabinet/admin/c2c-receipts/1/reject', json={'reason_key': 'because'})

        assert response.status_code == 400, response.text
        receipt = await db.get(C2cReceipt, 1)
        assert receipt.status == 'pending'


@pytest.mark.asyncio
async def test_a_failing_group_edit_never_fails_the_decision(monkeypatch):
    async with _client(monkeypatch) as (http, db, bot):
        bot.edit_message_text.side_effect = RuntimeError('chat not found')
        response = http.post('/cabinet/admin/c2c-receipts/1/approve', json={})

        assert response.status_code == 200, response.text
        assert await _balance(db) == 290_000


@pytest.mark.asyncio
async def test_reject_reasons_list_the_bot_catalog(monkeypatch):
    async with _client(monkeypatch) as (http, _db, _bot):
        response = http.get('/cabinet/admin/c2c-receipts/reject-reasons')

    assert response.status_code == 200, response.text
    codes = [item['code'] for item in response.json()]
    assert codes == ['amt_mismatch', 'unclear', 'wrong_card', 'duplicate', 'expired', 'silent']
    assert all(item['label'] for item in response.json())
