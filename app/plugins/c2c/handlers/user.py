"""User-facing C2C payment handlers."""

from __future__ import annotations

import html

import structlog
from aiogram import F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.config_helpers import format_card_message, get_next_card
from app.plugins.c2c.constants import (
    C2C_RECEIPT_TYPE_DOCUMENT,
    C2C_RECEIPT_TYPE_PHOTO,
    C2C_RECEIPT_TYPE_TEXT,
)
from app.plugins.c2c.service import C2cPaymentService
from app.plugins.c2c.states import C2cStates
from app.states import BalanceStates
from app.utils.decorators import error_handler


logger = structlog.get_logger(__name__)


async def _check_restriction_topup(callback: types.CallbackQuery, db_user: User) -> bool:
    """Return True if top-up is blocked for this user."""
    if not getattr(db_user, 'restriction_topup', False):
        return False

    texts = get_texts(db_user.language)
    reason = html.escape(getattr(db_user, 'restriction_reason', None) or 'Действие ограничено администратором')
    support_url = settings.get_support_contact_url()
    keyboard: list[list[types.InlineKeyboardButton]] = []
    if support_url:
        keyboard.append([types.InlineKeyboardButton(text='🆘 Обжаловать', url=support_url)])
    keyboard.append([types.InlineKeyboardButton(text=texts.BACK, callback_data='menu_balance')])

    await callback.message.edit_text(
        f'🚫 <b>Пополнение ограничено</b>\n\n{reason}\n\n'
        'Если вы считаете это ошибкой, вы можете обжаловать решение.',
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await callback.answer()
    return True


@error_handler
async def start_c2c_payment(callback: types.CallbackQuery, db_user: User, state: FSMContext) -> None:
    texts = get_texts(db_user.language)

    if await _check_restriction_topup(callback, db_user):
        return

    if not settings.is_c2c_enabled():
        await callback.answer(
            texts.t('CB_C2C_PAYMENT_UNAVAILABLE', '❌ Card-to-card payment is temporarily unavailable'),
            show_alert=True,
        )
        return

    if not settings.get_c2c_admin_chat_id():
        await callback.answer(
            texts.t('CB_C2C_ADMIN_NOT_CONFIGURED', '❌ Card-to-card payment is not configured'),
            show_alert=True,
        )
        return

    min_amount_rub = settings.C2C_MIN_AMOUNT_KOPEKS / 100
    max_amount_rub = settings.C2C_MAX_AMOUNT_KOPEKS / 100
    display_name = settings.get_c2c_display_name()

    message_text = texts.t(
        'C2C_ENTER_AMOUNT',
        '💳 <b>{name}</b>\n\nEnter top-up amount from {min:.0f} to {max:,.0f}:',
    ).format(name=display_name, min=min_amount_rub, max=max_amount_rub).replace(',', ' ')

    keyboard = get_back_keyboard(db_user.language)
    await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(BalanceStates.waiting_for_amount)
    await state.update_data(payment_method='c2c')
    await callback.answer()


@error_handler
async def process_c2c_payment_amount(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)

    if getattr(db_user, 'restriction_topup', False):
        reason = html.escape(getattr(db_user, 'restriction_reason', None) or 'Действие ограничено администратором')
        support_url = settings.get_support_contact_url()
        keyboard: list[list[types.InlineKeyboardButton]] = []
        if support_url:
            keyboard.append([types.InlineKeyboardButton(text='🆘 Обжаловать', url=support_url)])
        keyboard.append([types.InlineKeyboardButton(text=texts.BACK, callback_data='menu_balance')])
        await message.answer(
            f'🚫 <b>Пополнение ограничено</b>\n\n{reason}',
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
            parse_mode='HTML',
        )
        return

    if amount_kopeks < settings.C2C_MIN_AMOUNT_KOPEKS:
        min_rubles = settings.C2C_MIN_AMOUNT_KOPEKS / 100
        await message.answer(
            texts.t(
                'C2C_AMOUNT_TOO_LOW',
                '❌ Minimum amount for card-to-card: {min:.0f}',
            ).format(min=min_rubles),
            reply_markup=get_back_keyboard(db_user.language, callback_data='balance_topup'),
        )
        return

    if amount_kopeks > settings.C2C_MAX_AMOUNT_KOPEKS:
        max_rubles = settings.C2C_MAX_AMOUNT_KOPEKS / 100
        await message.answer(
            texts.t(
                'C2C_AMOUNT_TOO_HIGH',
                '❌ Maximum amount for card-to-card: {max:,.0f}',
            ).format(max=max_rubles).replace(',', ' '),
            reply_markup=get_back_keyboard(db_user.language, callback_data='balance_topup'),
        )
        return

    pending = await c2c_crud.get_pending_receipt_for_user(db, db_user.id)
    if pending:
        await message.answer(
            texts.t(
                'C2C_PENDING_RECEIPT_EXISTS',
                '⏳ You already have pending receipt #{id}. Wait for admin review or contact support.',
            ).format(id=pending.id),
            reply_markup=get_back_keyboard(db_user.language, callback_data='menu_balance'),
        )
        return

    try:
        card, card_index = await get_next_card()
    except ValueError:
        await message.answer(
            texts.t('CB_C2C_ADMIN_NOT_CONFIGURED', '❌ Card-to-card payment is not configured'),
            reply_markup=get_back_keyboard(db_user.language, callback_data='menu_balance'),
        )
        return

    receipt = await c2c_crud.create_pending_receipt(
        db,
        user_id=db_user.id,
        amount_kopeks=amount_kopeks,
        card_index=card_index,
        card_label=card.get('label'),
    )

    card_text = format_card_message(card, amount_kopeks, settings.C2C_GUIDE_TEXT)
    await message.answer(
        texts.t(
            'C2C_SEND_RECEIPT',
            '{card_info}\n\n📎 Send a photo, document, or text receipt after transfer.',
        ).format(card_info=card_text),
        parse_mode='HTML',
        reply_markup=get_back_keyboard(db_user.language, callback_data='menu_balance'),
    )

    await state.update_data(c2c_receipt_id=receipt.id)
    await state.set_state(C2cStates.waiting_for_receipt)


@error_handler
async def process_c2c_receipt(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    data = await state.get_data()
    receipt_id = data.get('c2c_receipt_id')

    if not receipt_id:
        await message.answer(
            texts.t('C2C_NO_ACTIVE_RECEIPT', '❌ No active card transfer session. Start again from balance menu.'),
            reply_markup=get_back_keyboard(db_user.language, callback_data='menu_balance'),
        )
        await state.clear()
        return

    receipt = await c2c_crud.get_c2c_receipt_by_id(db, int(receipt_id))
    if not receipt or receipt.user_id != db_user.id:
        await message.answer(
            texts.t('C2C_RECEIPT_NOT_FOUND', '❌ Receipt not found. Start card-to-card payment again.'),
            reply_markup=get_back_keyboard(db_user.language, callback_data='menu_balance'),
        )
        await state.clear()
        return

    pending_other = await c2c_crud.get_pending_receipt_for_user(db, db_user.id)
    if pending_other and pending_other.id != receipt.id:
        await message.answer(
            texts.t(
                'C2C_PENDING_RECEIPT_EXISTS',
                '⏳ You already have pending receipt #{id}.',
            ).format(id=pending_other.id),
        )
        return

    receipt_type: str | None = None
    receipt_file_id: str | None = None
    receipt_text: str | None = None

    if message.photo:
        receipt_type = C2C_RECEIPT_TYPE_PHOTO
        receipt_file_id = message.photo[-1].file_id
    elif message.document:
        receipt_type = C2C_RECEIPT_TYPE_DOCUMENT
        receipt_file_id = message.document.file_id
    elif message.text:
        receipt_type = C2C_RECEIPT_TYPE_TEXT
        receipt_text = message.text.strip()
    else:
        await message.answer(
            texts.t(
                'C2C_INVALID_RECEIPT',
                '❌ Send a photo, document, or text receipt (not stickers or voice).',
            ),
        )
        return

    service = C2cPaymentService(message.bot)
    success, error_message, _admin_msg_id = await service.submit_receipt(
        db,
        receipt=receipt,
        receipt_type=receipt_type,
        receipt_file_id=receipt_file_id,
        receipt_text=receipt_text,
        user_receipt_message_id=message.message_id,
        user=db_user,
    )

    if not success:
        await message.answer(
            texts.t('C2C_RECEIPT_SUBMIT_FAILED', '❌ Failed to submit receipt: {reason}').format(
                reason=error_message
            ),
        )
        return

    await message.answer(
        texts.t(
            'C2C_RECEIPT_SUBMITTED',
            '✅ Receipt #{id} submitted for review.\n\nYou will be notified when it is processed.',
        ).format(id=receipt.id),
        reply_markup=get_back_keyboard(db_user.language, callback_data='menu_balance'),
    )
    await state.clear()


def register_user_handlers(dp) -> None:
    from aiogram import Dispatcher

    assert isinstance(dp, Dispatcher)

    dp.callback_query.register(start_c2c_payment, F.data == 'topup_c2c')
    dp.message.register(
        process_c2c_receipt,
        C2cStates.waiting_for_receipt,
        F.photo | F.document | F.text,
    )
