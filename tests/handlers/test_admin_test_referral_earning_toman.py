"""Bot admin "test referral earning" (F-002): the typed amount is Toman, credited 1:1.

``balance_kopeks`` and ``ReferralEarning.amount_kopeks`` both hold Toman 1:1 (Phase B):
real earnings are written by ``referral_service`` with the same integer that
``add_user_balance`` credits. The test tool used to multiply the typed amount by 100.
"""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.handlers.admin.referrals as referrals_mod
from app.config import settings
from app.database.models import ReferralEarning


pytestmark = pytest.mark.asyncio

_CYRILLIC = re.compile('[Ѐ-ӿ]')
_PERSIAN_DIGITS = re.compile('[۰-۹]')


def _unwrap(fn):
    while hasattr(fn, '__wrapped__'):
        fn = fn.__wrapped__
    return fn


def _message(text: str) -> MagicMock:
    message = MagicMock()
    message.text = text
    message.answer = AsyncMock()
    return message


def _state() -> MagicMock:
    state = MagicMock()
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    return state


def _db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture(autouse=True)
def _test_mode_on(monkeypatch):
    monkeypatch.setattr(settings, 'REFERRAL_WITHDRAWAL_TEST_MODE', True)


async def _run(text: str, *, start_balance: int = 1_000_000, language: str = 'fa'):
    admin = SimpleNamespace(id=1, telegram_id=111, language=language)
    target = SimpleNamespace(id=7, telegram_id=123456789, full_name='Test User', balance_kopeks=start_balance)
    db = _db()
    message = _message(text)
    with (
        patch.object(referrals_mod, 'get_user_by_telegram_id', AsyncMock(return_value=target)),
        patch('app.database.crud.user.lock_user_for_update', AsyncMock(side_effect=lambda _db, user: user)),
    ):
        await _unwrap(referrals_mod.process_test_referral_earning)(message, admin, db, _state())
    return target, db, message


def _added_earning(db) -> ReferralEarning:
    earnings = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], ReferralEarning)]
    assert len(earnings) == 1
    return earnings[0]


async def test_credits_typed_toman_one_to_one() -> None:
    target, db, _ = await _run('123456789 50000')

    assert target.balance_kopeks == 1_050_000
    earning = _added_earning(db)
    assert earning.amount_kopeks == 50_000
    assert earning.reason == 'test_earning'


async def test_accepts_persian_digits_and_separators() -> None:
    target, db, _ = await _run('123456789 ۱٬۰۰۰٬۰۰۰', start_balance=0)

    assert target.balance_kopeks == 1_000_000
    assert _added_earning(db).amount_kopeks == 1_000_000


async def test_cap_is_ten_million_toman() -> None:
    target, db, _ = await _run('123456789 10000000', start_balance=0)
    assert target.balance_kopeks == 10_000_000

    target, db, message = await _run('123456789 10000001', start_balance=0)
    assert target.balance_kopeks == 0
    db.add.assert_not_called()
    reply = message.answer.await_args.args[0]
    assert settings.format_balance(10_000_000, language='fa') in reply


async def test_confirmation_shows_toman_in_persian() -> None:
    _, _, message = await _run('123456789 50000')

    reply = message.answer.await_args.args[0]
    assert settings.format_balance(50_000, language='fa') in reply
    assert settings.format_balance(1_050_000, language='fa') in reply
    assert 'واریز آزمایشی ثبت شد' in reply
    assert '₽' not in reply
    assert not _CYRILLIC.search(reply)
    assert not _PERSIAN_DIGITS.search(reply)


@pytest.mark.parametrize('text', ['123456789', '123456789 abc', '123456789 0', '123456789 -500'])
async def test_invalid_input_is_rejected_in_persian(text: str) -> None:
    target, db, message = await _run(text)

    assert target.balance_kopeks == 1_000_000
    db.add.assert_not_called()
    reply = message.answer.await_args.args[0]
    assert not _CYRILLIC.search(reply)


async def test_prompt_has_no_ruble_or_russian() -> None:
    admin = SimpleNamespace(id=1, telegram_id=111, language='fa')
    callback = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await _unwrap(referrals_mod.start_test_referral_earning)(callback, admin, _db(), _state())

    prompt = callback.message.edit_text.await_args.args[0]
    assert 'واریز آزمایشی درآمد معرفی' in prompt
    assert settings.format_balance(50_000, language='fa') in prompt
    assert '₽' not in prompt
    assert not _CYRILLIC.search(prompt)
    assert not _PERSIAN_DIGITS.search(prompt)
    keyboard = callback.message.edit_text.await_args.kwargs['reply_markup']
    assert not _CYRILLIC.search(keyboard.inline_keyboard[0][0].text)
