"""Bot Stars / CryptoBot top-up handlers quote from the fixed Toman rates (parity with the cabinet).

The bot's amount entry hands these handlers ``amount_kopeks`` = Toman x100 (typed Toman x 100 or a
quick-amount button on the same scale).
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.handlers.balance import cryptobot as cryptobot_handler, stars as stars_handler
from app.utils.toman_rates import parse_toman_topup_payload


def _user():
    return SimpleNamespace(id=42, telegram_id=111, language='fa', restriction_topup=False)


def _message():
    message = MagicMock()
    message.chat.id = 111
    message.message_id = 5
    message.answer = AsyncMock(return_value=SimpleNamespace(message_id=6, chat=SimpleNamespace(id=111)))
    message.delete = AsyncMock()
    message.bot = MagicMock()
    message.bot.delete_message = AsyncMock()
    return message


def _state():
    state = MagicMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


@pytest.fixture
def stars_service(monkeypatch):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', 1850, raising=False)
    service = MagicMock()
    service.create_stars_invoice = AsyncMock(return_value='https://t.me/$invoice')
    monkeypatch.setattr(stars_handler, 'PaymentService', lambda *_a, **_k: service)
    return service


@pytest.fixture
def crypto_service(monkeypatch):
    monkeypatch.setattr(settings, 'CRYPTOBOT_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_API_TOKEN', '1:test', raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_DEFAULT_ASSET', 'USDT', raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_TOMAN_PER_USDT', 95_000, raising=False)
    service = MagicMock()
    service.create_cryptobot_payment = AsyncMock(
        return_value={
            'invoice_id': '12345678',
            'local_payment_id': 3,
            'asset': 'USDT',
            'bot_invoice_url': 'https://t.me/CryptoBot?start=IV1',
        }
    )
    monkeypatch.setattr(cryptobot_handler, 'PaymentService', lambda *_a, **_k: service)
    return service


async def test_bot_stars_invoice_is_priced_in_toman(stars_service):
    message = _message()
    await stars_handler.process_stars_payment_amount(message, _user(), 5_000_000, _state())

    kwargs = stars_service.create_stars_invoice.await_args.kwargs
    assert kwargs['stars_amount'] == 28
    assert parse_toman_topup_payload(kwargs['payload']).toman == 51_800
    text = message.answer.await_args.args[0]
    assert '51,800' in text and '₽' not in text


async def test_bot_stars_refused_without_rate(stars_service, monkeypatch):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', None, raising=False)
    message = _message()
    await stars_handler.process_stars_payment_amount(message, _user(), 5_000_000, _state())
    stars_service.create_stars_invoice.assert_not_awaited()
    assert '₽' not in message.answer.await_args.args[0]


async def test_bot_cryptobot_invoice_is_priced_in_toman(crypto_service):
    message = _message()
    await cryptobot_handler.process_cryptobot_payment_amount(message, _user(), MagicMock(), 20_000_000, _state())

    kwargs = crypto_service.create_cryptobot_payment.await_args.kwargs
    assert Decimal(str(kwargs['amount_usd'])) == Decimal('2.11')
    assert kwargs['asset'] == 'USDT'
    assert parse_toman_topup_payload(kwargs['payload']).toman == 200_000
    text = message.answer.await_args.args[0]
    assert '200,000' in text and '₽' not in text


async def test_bot_cryptobot_below_min_names_toman(crypto_service):
    message = _message()
    await cryptobot_handler.process_cryptobot_payment_amount(message, _user(), MagicMock(), 5_000_000, _state())
    crypto_service.create_cryptobot_payment.assert_not_awaited()
    text = message.answer.await_args.args[0]
    assert '95,000' in text and '₽' not in text


@pytest.mark.parametrize(
    ('method', 'typed', 'expected_kopeks'),
    [('cryptobot', '۲۰۰,۰۰۰', 20_000_000), ('stars', '1000000', 100_000_000)],
)
async def test_typed_toman_reaches_toman_rate_handlers(monkeypatch, method, typed, expected_kopeks):
    from app.handlers.balance import main as balance_main

    routed: list[tuple[str, int]] = []

    async def _route(_message, _user, amount_kopeks, _state, payment_method):
        routed.append((payment_method, amount_kopeks))
        return True

    monkeypatch.setattr(balance_main, 'route_payment_by_method', _route)
    message = _message()
    message.text = typed
    message.successful_payment = None
    state = _state()
    state.get_data = AsyncMock(return_value={'payment_method': method})

    await balance_main.process_topup_amount(message, _user(), state)

    assert routed == [(method, expected_kopeks)]
