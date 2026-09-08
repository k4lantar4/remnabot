"""Cart-context top-up amount confirmation (suggested vs custom entry)."""

from __future__ import annotations

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.services.user_cart_service import user_cart_service
from app.states import BalanceStates
from app.utils.topup_suggestion import suggest_topup_amount_toman


async def _load_missing_toman(user_id: int, fallback: int) -> int:
    try:
        cart = await user_cart_service.get_user_cart(user_id)
        if cart and cart.get('missing_amount'):
            return int(cart['missing_amount'])
    except Exception:
        pass
    return fallback


async def get_cart_suggested_topup_amount(user_id: int) -> int:
    """Suggested top-up from saved cart, or 0 when no cart context."""
    from app.utils.topup_suggestion import resolve_suggested_topup_from_cart

    try:
        cart = await user_cart_service.get_user_cart(user_id)
        return resolve_suggested_topup_from_cart(cart)
    except Exception:
        return 0


from app.utils.cart_checkout_keyboard import prepend_return_to_checkout_row


async def _build_amount_prompt_keyboard(
    texts,
    *,
    user_id: int,
    method: str,
    suggested_amount: int,
    back_callback: str = 'balance_topup',
) -> InlineKeyboardMarkup:
    confirm_label = texts.t(
        'TOPUP_CONFIRM_SUGGESTED_BTN',
        '✅ Top up {amount}',
    ).format(amount=texts.format_balance(suggested_amount, round_kopeks=False))
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=confirm_label,
                callback_data=f'topup_confirm|{method}|{suggested_amount}',
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t('TOPUP_ENTER_CUSTOM_BTN', '✏️ Enter another amount'),
                callback_data=f'topup_custom|{method}',
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t('BACK', '◀️ Назад'),
                callback_data=back_callback,
            )
        ],
    ]
    await prepend_return_to_checkout_row(rows, user_id, texts)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_cart_topup_amount_prompt(
    callback: types.CallbackQuery,
    db_user: User,
    *,
    method: str,
    suggested_amount: int,
    back_callback: str = 'balance_topup',
    state: FSMContext | None = None,
) -> None:
    texts = get_texts(db_user.language)
    missing_toman = await _load_missing_toman(db_user.id, suggested_amount)
    if suggested_amount <= 0:
        suggested_amount = suggest_topup_amount_toman(missing_toman)

    message_text = texts.t(
        'TOPUP_AMOUNT_PROMPT_TITLE',
        '💳 <b>Top-up amount</b>\n\n'
        'Shortfall: {missing}\n'
        'Suggested top-up: <b>{suggested}</b> (rounded up to 1,000)\n\n'
        'Confirm the suggested amount or enter a custom value.',
    ).format(
        missing=texts.format_balance(missing_toman, round_kopeks=False),
        suggested=texts.format_balance(suggested_amount, round_kopeks=False),
    )

    keyboard = await _build_amount_prompt_keyboard(
        texts,
        user_id=db_user.id,
        method=method,
        suggested_amount=suggested_amount,
        back_callback=back_callback,
    )

    if state is not None:
        await state.update_data(payment_method=method)
        await state.set_state(BalanceStates.waiting_for_amount)

    await callback.answer()
    if isinstance(callback.message, types.Message):
        try:
            await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode='HTML')
        except Exception:
            await callback.message.answer(message_text, reply_markup=keyboard, parse_mode='HTML')


async def send_cart_topup_amount_prompt_message(
    message: types.Message,
    db_user: User,
    *,
    method: str,
    suggested_amount: int,
    back_callback: str = 'balance_topup',
) -> None:
    texts = get_texts(db_user.language)
    missing_toman = await _load_missing_toman(db_user.id, suggested_amount)
    if suggested_amount <= 0:
        suggested_amount = suggest_topup_amount_toman(missing_toman)

    message_text = texts.t(
        'TOPUP_AMOUNT_PROMPT_TITLE',
        '💳 <b>Top-up amount</b>\n\n'
        'Shortfall: {missing}\n'
        'Suggested top-up: <b>{suggested}</b> (rounded up to 1,000)\n\n'
        'Confirm the suggested amount or enter a custom value.',
    ).format(
        missing=texts.format_balance(missing_toman, round_kopeks=False),
        suggested=texts.format_balance(suggested_amount, round_kopeks=False),
    )

    keyboard = await _build_amount_prompt_keyboard(
        texts,
        user_id=db_user.id,
        method=method,
        suggested_amount=suggested_amount,
        back_callback=back_callback,
    )
    await message.answer(message_text, reply_markup=keyboard, parse_mode='HTML')


async def prompt_custom_topup_amount(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    *,
    method: str,
) -> None:
    texts = get_texts(db_user.language)
    await state.update_data(payment_method=method)
    await state.set_state(BalanceStates.waiting_for_amount)

    if method == 'c2c':
        from app.plugins.c2c.integration import build_c2c_topup_prompt

        message_text, keyboard = build_c2c_topup_prompt(db_user)
    else:
        message_text = texts.t(
            'TOPUP_CUSTOM_AMOUNT_PROMPT',
            '💳 Enter the top-up amount in chat.\n\nMinimum: {min_amount}',
        ).format(min_amount=texts.format_price(100))
        keyboard = get_back_keyboard(db_user.language, callback_data='balance_topup')

    await callback.answer()
    if isinstance(callback.message, types.Message):
        try:
            await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode='HTML')
        except Exception:
            await callback.message.answer(message_text, reply_markup=keyboard, parse_mode='HTML')
