"""Tests for cart-context top-up amount prompt keyboard."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from aiogram.types import InlineKeyboardButton

from app.handlers.balance.topup_prompt import _build_amount_prompt_keyboard


@pytest.mark.asyncio
async def test_amount_prompt_keyboard_includes_return_when_checkout_cart():
    texts = SimpleNamespace(
        RETURN_TO_SUBSCRIPTION_CHECKOUT='⬅️ Return',
        BACK='Back',
    )
    texts.t = lambda key, default=None, **kw: default.format(**kw) if kw and default else (default or key)
    texts.format_balance = lambda amount, **kw: str(amount)

    async def fake_prepend(rows, user_id, texts_arg):
        rows.insert(-1, [InlineKeyboardButton(text='Return', callback_data='return_to_saved_cart')])
        return True

    with patch(
        'app.handlers.balance.topup_prompt.prepend_return_to_checkout_row',
        side_effect=fake_prepend,
    ):
        keyboard = await _build_amount_prompt_keyboard(
            texts,
            user_id=7,
            method='c2c',
            suggested_amount=50_000,
        )

    callback_data = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert 'return_to_saved_cart' in callback_data
    assert 'topup_confirm|c2c|50000' in callback_data
