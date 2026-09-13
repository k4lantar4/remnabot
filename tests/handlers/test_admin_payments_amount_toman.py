"""F-088: the Telegram admin payments screens print a pending payment's amount in Toman.

Stars and Toman CryptoBot records carry plain Toman; the bot has no request and therefore no wire
scale, so what it prints and exports is that number as-is.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.config import settings
from app.database.models import PaymentMethod
from app.handlers.admin import payments
from app.services.payment_verification_service import PendingPayment


NOW = datetime(2026, 9, 12, tzinfo=UTC)


class _Texts:
    def t(self, _key, default=''):
        return default


def _pending(method: PaymentMethod, amount_toman: int) -> PendingPayment:
    return PendingPayment(
        method=method,
        local_id=7,
        identifier='tx-7',
        amount_kopeks=amount_toman,
        status='pending',
        is_paid=False,
        created_at=NOW,
        user=SimpleNamespace(id=1, telegram_id=42, username='u', full_name='U', email=None),
        payment=None,
        amount_is_toman=True,
    )


def test_list_line_prints_toman_for_a_stars_deposit() -> None:
    record = _pending(PaymentMethod.TELEGRAM_STARS, 50_000)

    text = '\n'.join(payments._build_record_lines(record, index=1, texts=_Texts(), language='fa'))

    assert f'— {settings.format_price(50_000)}' in text
    assert settings.format_price(5_000_000) not in text


def test_details_print_toman_for_a_cryptobot_invoice_without_crypto_amount() -> None:
    record = _pending(PaymentMethod.CRYPTOBOT, 1_000_000)

    text = payments._build_payment_details_text(record, texts=_Texts(), language='fa')

    assert settings.format_price(1_000_000) in text
    assert settings.format_price(100_000_000) not in text


async def test_export_amounts_are_toman(monkeypatch) -> None:
    record = _pending(PaymentMethod.TELEGRAM_STARS, 50_000)
    monkeypatch.setattr(payments, 'list_recent_pending_payments', AsyncMock(return_value=[record]))
    monkeypatch.setattr(payments, 'get_texts', lambda _lang: _Texts())
    callback = MagicMock()
    callback.message.answer_document = AsyncMock()
    callback.answer = AsyncMock()

    export = payments.export_payments.__wrapped__.__wrapped__
    await export(callback, db_user=SimpleNamespace(language='fa'), db=None)

    document = callback.message.answer_document.await_args.kwargs['document']
    (row,) = json.loads(document.data.decode('utf-8'))
    assert row['amount_kopeks'] == 50_000
    assert row['amount_rubles'] == 50_000
