"""The Stars pre-checkout accepts the Toman top-up payload; the success message shows the Toman credited."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers import stars_payments
from app.utils.toman_rates import build_toman_topup_payload


def _user(language='fa'):
    return SimpleNamespace(id=42, telegram_id=111, language=language)


async def test_pre_checkout_accepts_toman_topup_payload(monkeypatch):
    query = MagicMock()
    query.from_user.id = 111
    query.total_amount = 28
    query.invoice_payload = build_toman_topup_payload(42, 51_800, nonce=1)
    query.answer = AsyncMock()

    async def _get_user(_db, _tg_id):
        return _user()

    class _Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *exc):
            return False

    from app.database import database

    monkeypatch.setattr(database, 'AsyncSessionLocal', _Session)
    monkeypatch.setattr(stars_payments, 'get_user_by_telegram_id', _get_user)

    await stars_payments.handle_pre_checkout_query(query)

    query.answer.assert_awaited_once_with(ok=True)


@pytest.mark.parametrize('language', ['fa', 'en'])
async def test_success_message_shows_credited_toman(monkeypatch, language):
    message = MagicMock()
    message.from_user.id = 111
    message.chat.id = 111
    message.successful_payment = SimpleNamespace(
        total_amount=28,
        invoice_payload=build_toman_topup_payload(42, 51_800, nonce=1),
        telegram_payment_charge_id='charge-abcdef123',
    )
    message.answer = AsyncMock()

    async def _get_user(_db, _tg_id):
        return _user(language)

    service = MagicMock()
    service.process_stars_payment = AsyncMock(return_value=True)
    service.build_topup_success_keyboard = AsyncMock(return_value=None)

    async def _get_tx(_db, external_id, _method):
        assert external_id == 'charge-abcdef123'
        return SimpleNamespace(amount_kopeks=51_800, type='deposit')

    monkeypatch.setattr(stars_payments, 'get_user_by_telegram_id', _get_user)
    monkeypatch.setattr(stars_payments, 'PaymentService', lambda *_a, **_k: service)
    monkeypatch.setattr(stars_payments, 'get_transaction_by_external_id', _get_tx)

    state = MagicMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()

    await stars_payments.handle_successful_payment(message, db=object(), state=state)

    text = message.answer.await_args.args[0]
    assert '51,800' in text
    assert '₽' not in text
    assert '28' in text
