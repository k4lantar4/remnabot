"""User-facing C2C payment handlers."""

from __future__ import annotations

import html
from datetime import UTC, datetime, timedelta

import structlog
from aiogram import F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import C2cReceipt, C2cReceiptStatus, User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.config_helpers import format_card_message, get_card_by_index, get_next_card
from app.plugins.c2c.constants import (
    C2C_RECEIPT_TYPE_DOCUMENT,
    C2C_RECEIPT_TYPE_PHOTO,
    C2C_RECEIPT_TYPE_TEXT,
)
from app.plugins.c2c.integration import activate_c2c_topup_fsm, build_c2c_topup_prompt
from app.plugins.c2c.service import C2cPaymentService
from app.plugins.c2c.states import C2cStates
from app.utils.decorators import error_handler


logger = structlog.get_logger(__name__)


async def _resolve_c2c_receipt_for_user(
    db: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> tuple[C2cReceipt | None, str | None]:
    """Resolve pending receipt from FSM data or DB; sync FSM when recovered from DB."""
    data = await state.get_data()
    receipt_id = data.get('c2c_receipt_id')
    receipt: C2cReceipt | None = None

    if receipt_id is not None:
        try:
            receipt = await c2c_crud.get_c2c_receipt_by_id(db, int(receipt_id))
        except (TypeError, ValueError):
            receipt = None
        if receipt and receipt.user_id != db_user.id:
            receipt = None

    if receipt and receipt.status == C2cReceiptStatus.PENDING.value:
        return receipt, None

    pending = await c2c_crud.get_pending_receipt_for_user(db, db_user.id)
    if pending:
        await state.update_data(c2c_receipt_id=pending.id)
        await state.set_state(C2cStates.waiting_for_receipt)
        logger.info(
            'C2C receipt session recovered from pending row',
            user_id=db_user.id,
            receipt_id=pending.id,
            stale_fsm_receipt_id=receipt_id,
        )
        return pending, None

    if receipt_id is not None:
        return None, 'C2C_RECEIPT_NOT_FOUND'
    return None, 'C2C_NO_ACTIVE_RECEIPT'


async def _send_c2c_card_instructions(
    *,
    target: types.Message | types.CallbackQuery,
    db_user: User,
    receipt: C2cReceipt,
    state: FSMContext,
) -> None:
    """Show card details and switch FSM to waiting_for_receipt."""
    texts = get_texts(db_user.language)
    card = get_card_by_index(receipt.card_index)
    if card:
        card_text = format_card_message(card, receipt.amount_kopeks, settings.C2C_GUIDE_TEXT)
        body = texts.t(
            'C2C_SEND_RECEIPT',
            '{card_info}\n\n📎 Send a photo, document, or text receipt after transfer.',
        ).format(card_info=card_text)
    else:
        card_info = (
            f'💳 Pending transfer #{receipt.id}\n'
            f'💰 {settings.format_balance(receipt.amount_kopeks)}'
        )
        body = texts.t(
            'C2C_SEND_RECEIPT',
            '{card_info}\n\n📎 Send a photo, document, or text receipt after transfer.',
        ).format(card_info=card_info)

    keyboard = get_back_keyboard(db_user.language, callback_data='menu_balance')
    await state.update_data(c2c_receipt_id=receipt.id, payment_method='c2c')
    await state.set_state(C2cStates.waiting_for_receipt)

    message = target.message if isinstance(target, types.CallbackQuery) else target
    reply_markup = keyboard
    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(body, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await message.answer(body, parse_mode='HTML', reply_markup=reply_markup)


async def _check_restriction_topup(callback: types.CallbackQuery, db_user: User) -> bool:
    """Return True if top-up is blocked for this user."""
    if not getattr(db_user, 'restriction_topup', False):
        return False

    texts = get_texts(db_user.language)
    reason = html.escape(getattr(db_user, 'restriction_reason', None) or 'Действие ограничено администратором')
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

    await callback.message.edit_text(
        texts.t('BALANCE_RESTRICTED_TITLE', '🚫 <b>Пополнение ограничено</b>\n\n{reason}\n\n').format(reason=reason)
        + texts.t(
            'BALANCE_RESTRICTED_BODY',
            'Если вы считаете это ошибкой, вы можете обжаловать решение.',
        ),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await callback.answer()
    return True


@error_handler
async def start_c2c_payment(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
) -> None:
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

    message_text, keyboard = build_c2c_topup_prompt(db_user)
    await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode='HTML')
    await activate_c2c_topup_fsm(state)
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
        return

    if amount_kopeks < settings.C2C_MIN_AMOUNT_KOPEKS:
        await message.answer(
            texts.t(
                'C2C_AMOUNT_TOO_LOW',
                '❌ Minimum amount for card-to-card: {min}',
            ).format(min=texts.format_balance(settings.C2C_MIN_AMOUNT_KOPEKS)),
            reply_markup=get_back_keyboard(db_user.language, callback_data='balance_topup'),
        )
        return

    if amount_kopeks > settings.C2C_MAX_AMOUNT_KOPEKS:
        await message.answer(
            texts.t(
                'C2C_AMOUNT_TOO_HIGH',
                '❌ Maximum amount for card-to-card: {max}',
            ).format(max=texts.format_balance(settings.C2C_MAX_AMOUNT_KOPEKS)),
            reply_markup=get_back_keyboard(db_user.language, callback_data='balance_topup'),
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

    pending = await c2c_crud.get_pending_receipt_for_user(db, db_user.id)
    if pending:
        if pending.receipt_type:
            await message.answer(
                texts.t(
                    'C2C_PENDING_REVIEW',
                    '⏳ You already have receipt #{id} awaiting review. Please wait for admin decision.',
                ).format(id=pending.id),
                reply_markup=get_back_keyboard(db_user.language, callback_data='menu_balance'),
            )
            return
        pending.amount_kopeks = amount_kopeks
        pending.card_index = card_index
        pending.card_label = card.get('label')
        pending.expires_at = datetime.now(UTC) + timedelta(hours=settings.C2C_RECEIPT_TTL_HOURS)
        pending.updated_at = datetime.now(UTC)
        await db.flush()
        receipt = pending
    else:
        receipt = await c2c_crud.create_pending_receipt(
            db,
            user_id=db_user.id,
            amount_kopeks=amount_kopeks,
            card_index=card_index,
            card_label=card.get('label'),
        )

    await _send_c2c_card_instructions(target=message, db_user=db_user, receipt=receipt, state=state)
    await db.commit()


@error_handler
async def process_c2c_receipt(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    receipt, error_key = await _resolve_c2c_receipt_for_user(db, db_user, state)
    if not receipt:
        fallback = (
            '❌ Receipt not found. Start card-to-card payment again.'
            if error_key == 'C2C_RECEIPT_NOT_FOUND'
            else '❌ No active card transfer session. Start again from balance menu.'
        )
        await message.answer(
            texts.t(error_key or 'C2C_NO_ACTIVE_RECEIPT', fallback),
            reply_markup=get_back_keyboard(db_user.language, callback_data='menu_balance'),
        )
        await state.clear()
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
    elif message.text and not message.text.startswith('/'):
        receipt_text = message.text.strip()
        if not receipt_text:
            await message.answer(
                texts.t(
                    'C2C_INVALID_RECEIPT',
                    '❌ Send a photo, document, or text receipt (not stickers or voice).',
                ),
            )
            return
        receipt_type = C2C_RECEIPT_TYPE_TEXT
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
        F.photo | F.document | (F.text & ~F.text.startswith('/')),
    )
