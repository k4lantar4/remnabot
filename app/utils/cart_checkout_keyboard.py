"""Return-to-checkout button helpers for cart-context top-up flows."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.localization.texts import get_texts
from app.services.user_cart_service import user_cart_service


async def user_has_checkout_cart(user_id: int) -> bool:
    """True when the user has a saved cart from an explicit checkout flow."""
    try:
        cart = await user_cart_service.get_user_cart(user_id)
    except Exception:
        return False
    return bool(cart and cart.get('return_to_cart'))


def return_to_checkout_button(texts) -> InlineKeyboardButton:
    """Always a bot callback — never routed to cabinet WebApp."""
    return InlineKeyboardButton(
        text=texts.RETURN_TO_SUBSCRIPTION_CHECKOUT,
        callback_data='return_to_saved_cart',
    )


async def prepend_return_to_checkout_row(
    rows: list[list[InlineKeyboardButton]],
    user_id: int,
    texts,
) -> bool:
    """Insert return-to-checkout row before the last row (typically back). Returns True if inserted."""
    if not await user_has_checkout_cart(user_id):
        return False
    insert_at = max(0, len(rows) - 1)
    rows.insert(insert_at, [return_to_checkout_button(texts)])
    return True


async def build_back_keyboard_with_checkout(
    language: str,
    user_id: int,
    *,
    back_callback: str = 'menu_balance',
) -> InlineKeyboardMarkup:
    """Back row plus optional return-to-checkout when a checkout cart exists."""
    texts = get_texts(language)
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=texts.BACK, callback_data=back_callback)],
    ]
    await prepend_return_to_checkout_row(rows, user_id, texts)
    return InlineKeyboardMarkup(inline_keyboard=rows)
