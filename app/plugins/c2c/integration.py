"""Integration hooks for balance menu and payment routing."""

from __future__ import annotations

import html
from collections.abc import Callable

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.states import BalanceStates


def append_payment_button(
    keyboard: list[list[InlineKeyboardButton]],
    texts,
    build_callback: Callable[[str], str],
) -> bool:
    """Append C2C payment button when enabled."""
    if not settings.is_c2c_enabled():
        return False

    display_name = settings.get_c2c_display_name()
    keyboard.append(
        [
            InlineKeyboardButton(
                text=texts.t('PAYMENT_C2C', display_name),
                callback_data='topup_c2c',
            )
        ]
    )
    return True


async def route_c2c_payment(
    message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext,
) -> None:
    from app.plugins.c2c.handlers.user import process_c2c_payment_amount

    await process_c2c_payment_amount(message, db_user, db, amount_kopeks, state)


def build_c2c_topup_prompt(db_user: User) -> tuple[str, types.InlineKeyboardMarkup]:
    """Build C2C amount-entry prompt text and back keyboard."""
    texts = get_texts(db_user.language)
    display_name = settings.get_c2c_display_name()
    min_amount = texts.format_balance(settings.C2C_MIN_AMOUNT_KOPEKS)
    max_amount = texts.format_balance(settings.C2C_MAX_AMOUNT_KOPEKS)
    message_text = texts.t(
        'C2C_ENTER_AMOUNT',
        '💳 <b>{name}</b>\n\nEnter top-up amount:\nMinimum: {min_amount}\nMaximum: {max_amount}',
    ).format(name=display_name, min_amount=min_amount, max_amount=max_amount)
    keyboard = get_back_keyboard(db_user.language)
    return message_text, keyboard


async def activate_c2c_topup_fsm(state: FSMContext) -> None:
    """Set FSM state for C2C amount entry."""
    await state.set_state(BalanceStates.waiting_for_amount)
    await state.update_data(payment_method='c2c', c2c_receipt_id=None)


async def open_c2c_topup_from_message(
    message: types.Message,
    db_user: User,
    state: FSMContext,
) -> bool:
    """Shared entry: /start topup_c2c and cabinet deeplink. Returns True if prompt shown."""
    texts = get_texts(db_user.language)

    if getattr(db_user, 'restriction_topup', False):
        reason = html.escape(getattr(db_user, 'restriction_reason', None) or texts.t('USER_RESTRICTION_DEFAULT_REASON', 'Действие ограничено администратором'))
        support_url = settings.get_support_contact_url()
        keyboard: list[list[types.InlineKeyboardButton]] = []
        if support_url:
            keyboard.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t('BALANCE_RESTRICTED_APPEAL_BTN', '🆘 Обжаловать'),
                        url=support_url,
                    )
                ]
            )
        keyboard.append([types.InlineKeyboardButton(text=texts.BACK, callback_data='menu_balance')])
        await message.answer(
            texts.t('BALANCE_RESTRICTED_TITLE', '🚫 <b>Пополнение ограничено</b>\n\n{reason}\n\n').format(reason=reason)
            + texts.t(
                'BALANCE_RESTRICTED_BODY',
                'Если вы считаете это ошибкой, вы можете обжаловать решение.',
            ),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode='HTML',
        )
        return False

    if not settings.is_c2c_enabled():
        await message.answer(
            texts.t('CB_C2C_PAYMENT_UNAVAILABLE', '❌ Card-to-card payment is temporarily unavailable'),
        )
        return False

    if not settings.get_c2c_admin_chat_id():
        await message.answer(
            texts.t('CB_C2C_ADMIN_NOT_CONFIGURED', '❌ Card-to-card payment is not configured'),
        )
        return False

    message_text, keyboard = build_c2c_topup_prompt(db_user)
    await message.answer(message_text, reply_markup=keyboard, parse_mode='HTML')
    await activate_c2c_topup_fsm(state)
    return True
