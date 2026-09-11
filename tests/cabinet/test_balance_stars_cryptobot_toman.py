"""Cabinet Stars / CryptoBot top-ups quote from the fixed Toman rates and carry the Toman credit.

The cabinet sends ``amount_kopeks`` = Toman x100 (TopUpAmount.tsx). The balance is Toman 1:1, so
the invoice must be priced for amount/100 Toman and its payload must name that Toman credit.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.cabinet.routes import balance as balance_routes
from app.cabinet.schemas.balance import PaymentMethodResponse, StarsInvoiceRequest, TopUpRequest
from app.config import settings
from app.utils.toman_rates import parse_toman_topup_payload


def _user(**overrides):
    data = {'id': 42, 'telegram_id': 111, 'language': 'en', 'restriction_topup': False, 'username': 'u'}
    data.update(overrides)
    return SimpleNamespace(**data)


def _method(method_id: str, min_kopeks: int, max_kopeks: int) -> PaymentMethodResponse:
    return PaymentMethodResponse(
        id=method_id,
        name=method_id,
        min_amount_kopeks=min_kopeks,
        max_amount_kopeks=max_kopeks,
        is_available=True,
    )


@pytest.fixture
def stars_env(monkeypatch):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', 1850, raising=False)
    monkeypatch.setattr(
        balance_routes,
        'get_payment_methods',
        AsyncMock(return_value=[_method('telegram_stars', 185_000, 1_850_000_000)]),
    )
    bot = MagicMock()
    bot.create_invoice_link = AsyncMock(return_value='https://t.me/$invoice')

    @asynccontextmanager
    async def _fake_bot():
        yield bot

    monkeypatch.setattr(balance_routes, 'create_bot', _fake_bot)
    return bot


@pytest.fixture
def cryptobot_env(monkeypatch):
    monkeypatch.setattr(settings, 'CRYPTOBOT_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_API_TOKEN', '1:test', raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_DEFAULT_ASSET', 'USDT', raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_TOMAN_PER_USDT', 95_000, raising=False)
    monkeypatch.setattr(
        balance_routes,
        'get_payment_methods',
        AsyncMock(return_value=[_method('cryptobot', 9_500_000, 9_500_000_000)]),
    )
    service = MagicMock()
    service.create_cryptobot_payment = AsyncMock(
        return_value={'invoice_id': '99', 'bot_invoice_url': 'https://t.me/CryptoBot?start=IV99'}
    )
    monkeypatch.setattr(balance_routes, 'PaymentService', lambda *a, **k: service)
    return service


# ---- Stars ----------------------------------------------------------------


async def test_stars_invoice_prices_toman_and_payload_carries_credit(stars_env):
    response = await balance_routes.create_stars_invoice(
        StarsInvoiceRequest(amount_kopeks=5_000_000), user=_user(), db=MagicMock()
    )

    kwargs = stars_env.create_invoice_link.await_args.kwargs
    # 50,000 T at 1,850 T/star → 28 stars, worth 51,800 T.
    assert kwargs['prices'][0].amount == 28
    assert kwargs['currency'] == 'XTR'
    parsed = parse_toman_topup_payload(kwargs['payload'])
    assert parsed is not None and parsed.user_id == 42 and parsed.toman == 51_800
    assert '₽' not in kwargs['description'] and 'RUB' not in kwargs['description']
    assert response.stars_amount == 28
    assert response.amount_kopeks == 5_180_000


async def test_stars_invoice_million_toman(stars_env):
    await balance_routes.create_stars_invoice(
        StarsInvoiceRequest(amount_kopeks=100_000_000), user=_user(), db=MagicMock()
    )
    kwargs = stars_env.create_invoice_link.await_args.kwargs
    assert kwargs['prices'][0].amount == 541  # ceil(1,000,000 / 1,850)
    assert parse_toman_topup_payload(kwargs['payload']).toman == 1_000_850


async def test_stars_invoice_below_min_is_refused_in_toman(stars_env):
    with pytest.raises(HTTPException) as exc:
        await balance_routes.create_stars_invoice(
            StarsInvoiceRequest(amount_kopeks=100_000), user=_user(), db=MagicMock()
        )
    assert exc.value.status_code == 400
    assert 'RUB' not in exc.value.detail
    assert '1,850' in exc.value.detail
    stars_env.create_invoice_link.assert_not_awaited()


async def test_stars_invoice_refused_when_method_not_offered(stars_env, monkeypatch):
    monkeypatch.setattr(balance_routes, 'get_payment_methods', AsyncMock(return_value=[]))
    with pytest.raises(HTTPException) as exc:
        await balance_routes.create_stars_invoice(
            StarsInvoiceRequest(amount_kopeks=5_000_000), user=_user(), db=MagicMock()
        )
    assert exc.value.status_code == 400
    stars_env.create_invoice_link.assert_not_awaited()


async def test_stars_invoice_refused_for_restricted_user(stars_env):
    with pytest.raises(HTTPException) as exc:
        await balance_routes.create_stars_invoice(
            StarsInvoiceRequest(amount_kopeks=5_000_000), user=_user(restriction_topup=True), db=MagicMock()
        )
    assert exc.value.status_code == 403


# ---- CryptoBot ------------------------------------------------------------


async def test_cryptobot_topup_quotes_usdt_from_toman_rate(cryptobot_env):
    response = await balance_routes.create_topup(
        TopUpRequest(amount_kopeks=20_000_000, payment_method='cryptobot'), user=_user(), db=MagicMock()
    )

    kwargs = cryptobot_env.create_cryptobot_payment.await_args.kwargs
    assert Decimal(str(kwargs['amount_usd'])) == Decimal('2.11')  # 200,000 / 95,000 rounded up
    assert kwargs['asset'] == 'USDT'
    parsed = parse_toman_topup_payload(kwargs['payload'])
    assert parsed is not None and parsed.user_id == 42 and parsed.toman == 200_000
    assert '₽' not in kwargs['description']
    assert response.payment_url == 'https://t.me/CryptoBot?start=IV99'


async def test_cryptobot_topup_million_toman(cryptobot_env):
    await balance_routes.create_topup(
        TopUpRequest(amount_kopeks=100_000_000, payment_method='cryptobot'), user=_user(), db=MagicMock()
    )
    kwargs = cryptobot_env.create_cryptobot_payment.await_args.kwargs
    assert Decimal(str(kwargs['amount_usd'])) == Decimal('10.53')
    assert parse_toman_topup_payload(kwargs['payload']).toman == 1_000_000


async def test_cryptobot_topup_refused_without_rate(cryptobot_env, monkeypatch):
    monkeypatch.setattr(settings, 'CRYPTOBOT_TOMAN_PER_USDT', None, raising=False)
    with pytest.raises(HTTPException) as exc:
        await balance_routes.create_topup(
            TopUpRequest(amount_kopeks=20_000_000, payment_method='cryptobot'), user=_user(), db=MagicMock()
        )
    assert exc.value.status_code == 400
    assert 'not available' in exc.value.detail
    cryptobot_env.create_cryptobot_payment.assert_not_awaited()


async def test_topup_range_error_is_toman_not_rubles(cryptobot_env):
    # 50,000 T is below the 1 USDT (= 95,000 T) CryptoBot minimum.
    with pytest.raises(HTTPException) as exc:
        await balance_routes.create_topup(
            TopUpRequest(amount_kopeks=5_000_000, payment_method='cryptobot'), user=_user(), db=MagicMock()
        )
    assert exc.value.status_code == 400
    assert 'RUB' not in exc.value.detail
    assert '95,000' in exc.value.detail
