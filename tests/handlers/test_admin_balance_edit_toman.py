"""Bot admin: balance edit credits the typed Toman 1:1; the user card shows Toman."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import app.handlers.admin.users as users_mod
from app.config import settings


def _unwrap(fn):
    while hasattr(fn, '__wrapped__'):
        fn = fn.__wrapped__
    return fn


def _message(text: str) -> MagicMock:
    message = MagicMock()
    message.text = text
    message.answer = AsyncMock()
    message.bot = MagicMock()
    return message


def _state(user_id: int = 7833) -> MagicMock:
    state = MagicMock()
    state.get_data = AsyncMock(return_value={'editing_user_id': user_id})
    state.clear = AsyncMock()
    return state


async def _run_edit(text: str):
    admin = SimpleNamespace(id=433, language='fa', full_name='Admin')
    target = SimpleNamespace(id=7833, language='fa', balance_kopeks=0)
    service = MagicMock()
    service.update_user_balance = AsyncMock(return_value=True)
    message = _message(text)
    with (
        patch.object(users_mod, 'UserService', return_value=service),
        patch.object(users_mod, 'get_user_by_id', AsyncMock(return_value=target)),
    ):
        await _unwrap(users_mod.process_balance_edit)(message, admin, _state(), AsyncMock())
    return service, message


async def test_topup_credits_typed_toman() -> None:
    service, _ = await _run_edit('200000')

    args = service.update_user_balance.await_args.args
    assert args[2] == 200_000


async def test_deduction_with_persian_digits_and_separators() -> None:
    service, _ = await _run_edit('-۵۰٬۰۰۰')

    assert service.update_user_balance.await_args.args[2] == -50_000


async def test_success_reply_shows_toman_amount() -> None:
    _, message = await _run_edit('1000000')

    reply = message.answer.await_args.args[0]
    assert settings.format_balance(1_000_000) in reply
    assert '₽' not in reply


async def test_ledger_description_has_no_ruble_sign() -> None:
    service, _ = await _run_edit('50000')

    description = service.update_user_balance.await_args.args[3]
    assert '₽' not in description
    assert settings.format_balance(50_000, language='fa') in description


async def test_over_cap_rejected_without_crediting() -> None:
    service, message = await _run_edit('10000001')

    service.update_user_balance.assert_not_awaited()
    assert '₽' not in message.answer.await_args.args[0]


async def test_user_transactions_card_renders_every_type_on_one_scale() -> None:
    """Phase C: a deposit and a subscription charge of the same size read the same.

    The card used to pick a scale per transaction type — deposits 1:1, catalog charges divided by
    100 — so these two rows rendered 100x apart. `_BALANCE_SCALE_TRANSACTION_TYPES` is gone with
    that split, and a type that nobody remembered to classify can no longer render 100x off.
    """
    user = SimpleNamespace(id=7833, telegram_id=6371108688, email=None, balance_kopeks=172_700, full_name='Ali')
    transactions = [
        SimpleNamespace(
            amount_kopeks=1_000_000, type='deposit', description='c2c', created_at=datetime(2026, 9, 10, tzinfo=UTC)
        ),
        SimpleNamespace(
            amount_kopeks=-1_000_000,
            type='subscription_payment',
            description='روزانه',
            created_at=datetime(2026, 9, 10, tzinfo=UTC),
        ),
    ]
    callback = MagicMock()
    callback.data = 'admin_user_transactions_7833'
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    with (
        patch.object(users_mod, 'get_user_by_id', AsyncMock(return_value=user)),
        patch('app.database.crud.transaction.get_user_transactions', AsyncMock(return_value=transactions)),
    ):
        await _unwrap(users_mod.show_user_transactions)(callback, SimpleNamespace(language='fa'), AsyncMock())

    text = callback.message.edit_text.await_args.args[0]
    assert settings.format_balance(172_700) in text
    assert text.count(settings.format_balance(1_000_000)) == 2, 'both rows read their stored Toman'
    assert settings.format_balance(10_000) not in text, 'no type is divided by 100 any more'
