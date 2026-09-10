"""User notification after an admin balance change shows Toman 1:1 (balance scale)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.user_service import UserService


async def _notify(amount: int, balance: int):
    user = SimpleNamespace(id=7833, language='fa', balance_kopeks=balance, subscriptions=[], telegram_id=6371108688)
    send = AsyncMock(return_value=True)
    with patch('app.services.user_service.notification_delivery_service.send_notification', send):
        await UserService()._send_balance_notification(MagicMock(), user, amount, 'Admin')
    return send.await_args.kwargs


async def test_credit_notification_shows_toman() -> None:
    kwargs = await _notify(200_000, 1_050_000)

    message = kwargs['telegram_message']
    assert '200,000' in message
    assert '1,050,000' in message
    assert '₽' not in message
    assert kwargs['context']['amount_rubles'] == 200_000
    assert kwargs['context']['new_balance_rubles'] == 1_050_000
    assert '1,050,000' in kwargs['context']['formatted_balance']


async def test_debit_notification_shows_toman() -> None:
    kwargs = await _notify(-50_000, 1_000_000)

    message = kwargs['telegram_message']
    assert '50,000' in message
    assert '1,000,000' in message
    assert '₽' not in message
    assert '50,000' in kwargs['context']['formatted_amount']
