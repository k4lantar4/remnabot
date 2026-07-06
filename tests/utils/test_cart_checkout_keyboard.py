"""Tests for cart checkout return-to-checkout keyboard helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.utils.cart_checkout_keyboard import (
    prepend_return_to_checkout_row,
    return_to_checkout_button,
    user_has_checkout_cart,
)


@pytest.mark.asyncio
async def test_user_has_checkout_cart_true_when_return_to_cart():
    with patch('app.utils.cart_checkout_keyboard.user_cart_service') as mock_cart:
        mock_cart.get_user_cart = AsyncMock(return_value={'return_to_cart': True, 'cart_mode': 'tariff_purchase'})
        assert await user_has_checkout_cart(42) is True


@pytest.mark.asyncio
async def test_user_has_checkout_cart_false_without_return_flag():
    with patch('app.utils.cart_checkout_keyboard.user_cart_service') as mock_cart:
        mock_cart.get_user_cart = AsyncMock(return_value={'saved_cart': True})
        assert await user_has_checkout_cart(42) is False


@pytest.mark.asyncio
async def test_prepend_return_to_checkout_row_inserts_before_back():
    from types import SimpleNamespace

    from aiogram.types import InlineKeyboardButton

    texts = SimpleNamespace(RETURN_TO_SUBSCRIPTION_CHECKOUT='⬅️ Return')
    rows = [[InlineKeyboardButton(text='Back', callback_data='menu_balance')]]
    with patch('app.utils.cart_checkout_keyboard.user_has_checkout_cart', AsyncMock(return_value=True)):
        inserted = await prepend_return_to_checkout_row(rows, 1, texts)

    assert inserted is True
    assert len(rows) == 2
    assert rows[0][0].callback_data == 'return_to_saved_cart'
    assert rows[1][0].callback_data == 'menu_balance'


def test_return_to_checkout_button_uses_callback_not_webapp():
    from types import SimpleNamespace

    texts = SimpleNamespace(RETURN_TO_SUBSCRIPTION_CHECKOUT='⬅️ Return')
    button = return_to_checkout_button(texts)
    assert button.callback_data == 'return_to_saved_cart'
    assert button.web_app is None
