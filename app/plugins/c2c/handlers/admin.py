"""Admin C2C approve/reject handlers."""

from __future__ import annotations

from typing import Any

import structlog
from aiogram import F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import C2cReceipt, C2cReceiptStatus, User
from app.localization.texts import get_texts
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.admin_messages import (
    build_c2c_admin_receipt_body,
    build_c2c_resolved_keyboard,
)
from app.plugins.c2c.constants import (
    C2C_CALLBACK_APPROVE_PREFIX,
    C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX,
    C2C_CALLBACK_REJECT_PREFIX,
    C2C_CALLBACK_REJECT_REASON_PREFIX,
    C2C_CALLBACK_RESTORE_REVIEW_PREFIX,
    C2C_CALLBACK_RESOLVED_PREFIX,
)
from app.plugins.c2c.handlers.admin_inbox import send_inbox_list_message
from app.plugins.c2c.keyboards import get_c2c_admin_review_keyboard, get_c2c_reject_reason_keyboard
from app.plugins.c2c.reject_reasons import C2C_REJECT_REASONS
from app.plugins.c2c.service import C2cPaymentService, get_c2c_fsm_storage
from app.states import AdminStates
from app.utils.decorators import admin_required, error_handler
from app.utils.price_display import balance_from_display_amount


logger = structlog.get_logger(__name__)


def _parse_receipt_id(callback_data: str, prefix: str) -> int | None:
    if not callback_data.startswith(prefix):
        return None
    try:
        return int(callback_data[len(prefix) :])
    except ValueError:
        return None


def _parse_reject_reason_callback(callback_data: str) -> tuple[int, str] | None:
    if not callback_data.startswith(C2C_CALLBACK_REJECT_REASON_PREFIX):
        return None
    remainder = callback_data[len(C2C_CALLBACK_REJECT_REASON_PREFIX) :]
    if ':' not in remainder:
        return None
    receipt_part, reason_code = remainder.split(':', 1)
    if reason_code not in C2C_REJECT_REASONS:
        return None
    try:
        return int(receipt_part), reason_code
    except ValueError:
        return None


def _admin_chat_ok(callback: types.CallbackQuery) -> bool:
    admin_chat_id = settings.get_c2c_admin_chat_id()
    if not admin_chat_id or not callback.message:
        return False
    return callback.message.chat.id == admin_chat_id


async def _edit_callback_message(
    callback: types.CallbackQuery,
    text: str,
    *,
    reply_markup=None,
) -> None:
    if not callback.message:
        return
    try:
        if callback.message.text:
            await callback.message.edit_text(text, parse_mode='HTML', reply_markup=reply_markup)
        elif callback.message.caption is not None:
            await callback.message.edit_caption(caption=text, parse_mode='HTML', reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if 'message is not modified' not in str(error).lower():
            logger.warning('Could not edit C2C admin message', error=error)


async def sync_c2c_group_admin_message(
    bot: types.Bot,
    receipt: C2cReceipt,
    *,
    status_html: str,
    reply_markup=None,
    skip_message_id: int | None = None,
) -> None:
    """Update stored admin supergroup receipt post after inbox action."""
    admin_chat_id = receipt.admin_chat_id
    admin_message_id = receipt.admin_message_id
    if not admin_chat_id or not admin_message_id:
        return
    if skip_message_id is not None and skip_message_id == admin_message_id:
        return

    chat_id = int(admin_chat_id)
    message_id = int(admin_message_id)
    try:
        await bot.edit_message_text(
            text=status_html,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode='HTML',
        )
    except TelegramBadRequest as error:
        error_message = str(error).lower()
        if 'message is not modified' in error_message:
            return
        if 'there is no text in the message to edit' not in error_message:
            logger.warning(
                'Could not sync C2C group admin message (text)',
                receipt_id=receipt.id,
                chat_id=chat_id,
                message_id=message_id,
                error=error,
            )
            return
        try:
            await bot.edit_message_caption(
                caption=status_html,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
                parse_mode='HTML',
            )
        except TelegramBadRequest as caption_error:
            if 'message is not modified' not in str(caption_error).lower():
                logger.warning(
                    'Could not sync C2C group admin message (caption)',
                    receipt_id=receipt.id,
                    chat_id=chat_id,
                    message_id=message_id,
                    error=caption_error,
                )


def _callback_skip_group_sync_message_id(callback: types.CallbackQuery) -> int | None:
    if _admin_chat_ok(callback) and callback.message:
        return callback.message.message_id
    return None


def _admin_label(callback: types.CallbackQuery | types.Message, admin_telegram_id: int) -> str:
    user = callback.from_user
    if user:
        return user.username or str(user.id)
    return str(admin_telegram_id)


async def _refresh_private_inbox_after_action(
    callback: types.CallbackQuery,
    db: AsyncSession,
) -> None:
    if _admin_chat_ok(callback) or not callback.bot or not callback.message:
        return
    lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
    await send_inbox_list_message(
        callback.bot,
        callback.message.chat.id,
        db,
        lang,
    )


async def _resolved_receipt_message(
    db: AsyncSession,
    receipt: C2cReceipt,
    admin_label: str,
    *,
    include_inbox_back: bool = False,
) -> tuple[str, types.InlineKeyboardMarkup]:
    lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
    receipt_with_user = await c2c_crud.get_c2c_receipt_with_user(db, receipt.id)
    if receipt_with_user is not None:
        receipt = receipt_with_user
    body = build_c2c_admin_receipt_body(
        receipt,
        receipt.user,
        lang=lang,
        admin_label=admin_label,
    )
    keyboard = build_c2c_resolved_keyboard(
        receipt.id,
        receipt.status,
        lang=lang,
        include_inbox_back=include_inbox_back,
    )
    return body, keyboard


async def on_c2c_resolved_tap(callback: types.CallbackQuery) -> None:
    try:
        await callback.answer('Already processed', show_alert=True)
    except TelegramBadRequest:
        pass


async def _notify_c2c_already_processed(callback: types.CallbackQuery) -> None:
    try:
        await callback.answer('Already processed', show_alert=True)
    except TelegramBadRequest:
        pass


async def _set_custom_amount_state(
    *,
    bot_id: int,
    chat_id: int,
    user_id: int,
    receipt_id: int,
) -> None:
    storage = get_c2c_fsm_storage()
    if not storage:
        return
    key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)
    await storage.set_state(key=key, state=AdminStates.c2c_custom_amount)
    await storage.set_data(key=key, data={'c2c_custom_receipt_id': receipt_id})


async def _clear_custom_amount_state(*, bot_id: int, chat_id: int, user_id: int) -> None:
    storage = get_c2c_fsm_storage()
    if not storage:
        return
    key = StorageKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)
    await storage.set_state(key=key, state=None)
    await storage.set_data(key=key, data={})


async def _execute_c2c_custom_amount_input(
    message: types.Message,
    db: AsyncSession,
    *,
    receipt_id: int,
    language: str,
) -> None:
    if not message.from_user:
        return

    texts = get_texts(language)

    if not message.text:
        await message.answer(
            texts.t('C2C_ADMIN_CUSTOM_AMOUNT_INVALID', '❌ Invalid amount. Enter an integer.'),
        )
        return

    try:
        amount_kopeks = balance_from_display_amount(message.text.strip())
    except ValueError:
        await message.answer(
            texts.t('C2C_ADMIN_CUSTOM_AMOUNT_INVALID', '❌ Invalid amount. Enter an integer.'),
        )
        return

    if amount_kopeks < settings.C2C_MIN_AMOUNT_KOPEKS or amount_kopeks > settings.C2C_MAX_AMOUNT_KOPEKS:
        await message.answer(
            texts.t(
                'C2C_ADMIN_CUSTOM_AMOUNT_OUT_OF_RANGE',
                '❌ Amount must be between {min} and {max}.',
            ).format(
                min=texts.format_balance(settings.C2C_MIN_AMOUNT_KOPEKS),
                max=texts.format_balance(settings.C2C_MAX_AMOUNT_KOPEKS),
            ),
        )
        return

    service = C2cPaymentService(message.bot)
    success, status_message, receipt = await service.approve_receipt(
        db,
        receipt_id,
        message.from_user.id,
        credited_amount_kopeks=amount_kopeks,
    )
    await _clear_custom_amount_state(
        bot_id=message.bot.id,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
    )

    if not success:
        await message.answer(f'❌ {status_message}')
        return

    credit_display = settings.format_balance(receipt.approved_amount_kopeks if receipt else amount_kopeks)
    if receipt and message.bot:
        label = _admin_label(message, message.from_user.id)
        body, keyboard = await _resolved_receipt_message(db, receipt, label)
        await sync_c2c_group_admin_message(
            message.bot,
            receipt,
            status_html=body,
            reply_markup=keyboard,
        )
    await message.answer(
        f'✅ Receipt #{receipt_id} approved for {credit_display}',
        parse_mode='HTML',
    )


async def execute_c2c_approve(
    callback: types.CallbackQuery,
    db: AsyncSession,
    admin_telegram_id: int,
    *,
    credited_amount_kopeks: int | None = None,
) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_APPROVE_PREFIX)
    if receipt_id is None:
        return

    service = C2cPaymentService(callback.bot)
    success, message, receipt = await service.approve_receipt(
        db,
        receipt_id,
        admin_telegram_id,
        credited_amount_kopeks=credited_amount_kopeks,
    )

    if not success:
        logger.warning('C2C approve failed', receipt_id=receipt_id, message=message)
        if message == 'Already processed' and receipt and callback.bot:
            label = _admin_label(callback, admin_telegram_id)
            include_inbox_back = not _admin_chat_ok(callback)
            body, keyboard = await _resolved_receipt_message(
                db,
                receipt,
                label,
                include_inbox_back=include_inbox_back,
            )
            await sync_c2c_group_admin_message(
                callback.bot,
                receipt,
                status_html=body,
                reply_markup=keyboard,
                skip_message_id=_callback_skip_group_sync_message_id(callback),
            )
            if _admin_chat_ok(callback):
                await _notify_c2c_already_processed(callback)
        return

    label = _admin_label(callback, admin_telegram_id)
    if receipt and receipt.status == C2cReceiptStatus.APPROVED.value:
        include_inbox_back = not _admin_chat_ok(callback)
        body, keyboard = await _resolved_receipt_message(
            db,
            receipt,
            label,
            include_inbox_back=include_inbox_back,
        )
        await _edit_callback_message(callback, body, reply_markup=keyboard)
        if callback.bot:
            await sync_c2c_group_admin_message(
                callback.bot,
                receipt,
                status_html=body,
                reply_markup=keyboard,
                skip_message_id=_callback_skip_group_sync_message_id(callback),
            )
        await _refresh_private_inbox_after_action(callback, db)


async def execute_c2c_reject(
    callback: types.CallbackQuery,
    db: AsyncSession,
    admin_telegram_id: int,
    *,
    reason_key: str | None = None,
) -> None:
    parsed = _parse_reject_reason_callback(callback.data or '')
    if parsed is not None:
        receipt_id, reason_key = parsed
    else:
        receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_REJECT_PREFIX)

    if receipt_id is None:
        return

    service = C2cPaymentService(callback.bot)
    success, message, receipt = await service.reject_receipt(
        db,
        receipt_id,
        admin_telegram_id,
        reason_key=reason_key,
    )

    if not success:
        logger.warning('C2C reject failed', receipt_id=receipt_id, message=message)
        if message == 'Already processed' and receipt and callback.bot:
            label = _admin_label(callback, admin_telegram_id)
            include_inbox_back = not _admin_chat_ok(callback)
            body, keyboard = await _resolved_receipt_message(
                db,
                receipt,
                label,
                include_inbox_back=include_inbox_back,
            )
            await sync_c2c_group_admin_message(
                callback.bot,
                receipt,
                status_html=body,
                reply_markup=keyboard,
                skip_message_id=_callback_skip_group_sync_message_id(callback),
            )
            if _admin_chat_ok(callback):
                await _notify_c2c_already_processed(callback)
        return

    label = _admin_label(callback, admin_telegram_id)
    if receipt and receipt.status == C2cReceiptStatus.REJECTED.value:
        include_inbox_back = not _admin_chat_ok(callback)
        body, keyboard = await _resolved_receipt_message(
            db,
            receipt,
            label,
            include_inbox_back=include_inbox_back,
        )
        await _edit_callback_message(callback, body, reply_markup=keyboard)
        if callback.bot:
            await sync_c2c_group_admin_message(
                callback.bot,
                receipt,
                status_html=body,
                reply_markup=keyboard,
                skip_message_id=_callback_skip_group_sync_message_id(callback),
            )
        await _refresh_private_inbox_after_action(callback, db)


async def show_c2c_reject_menu(
    callback: types.CallbackQuery,
    db: AsyncSession,
) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_REJECT_PREFIX)
    if receipt_id is None:
        return

    receipt = await c2c_crud.get_c2c_receipt_with_user(db, receipt_id)
    if not receipt:
        return

    lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
    texts = get_texts(lang)
    body = texts.t(
        'C2C_ADMIN_REJECT_MENU_TITLE',
        '❌ <b>Reject receipt #{id}</b>\n\nSelect a reason:',
    ).format(id=receipt_id)
    keyboard = get_c2c_reject_reason_keyboard(receipt_id, language=lang)
    await _edit_callback_message(callback, body, reply_markup=keyboard)


async def restore_c2c_review_keyboard(
    callback: types.CallbackQuery,
    db: AsyncSession,
) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_RESTORE_REVIEW_PREFIX)
    if receipt_id is None:
        return

    receipt = await c2c_crud.get_c2c_receipt_with_user(db, receipt_id)
    if not receipt:
        return

    lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
    amount_display = settings.format_balance(receipt.amount_kopeks)
    body = build_c2c_admin_receipt_body(receipt, receipt.user, lang=lang)
    keyboard = get_c2c_admin_review_keyboard(receipt_id, amount_display, language=lang)
    await _edit_callback_message(callback, body, reply_markup=keyboard)


async def start_c2c_custom_amount(
    callback: types.CallbackQuery,
    db: AsyncSession,
) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX)
    if receipt_id is None or not callback.message or not callback.from_user:
        return

    receipt = await c2c_crud.get_c2c_receipt_with_user(db, receipt_id)
    if not receipt:
        return

    lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
    texts = get_texts(lang)
    amount_display = settings.format_balance(receipt.amount_kopeks)
    prompt = texts.t(
        'C2C_ADMIN_CUSTOM_AMOUNT_PROMPT',
        '💰 <b>Custom approve amount</b>\n\nReceipt #{id} — requested: {requested}\n\nEnter amount to credit (Toman):',
    ).format(id=receipt_id, requested=amount_display)

    await _set_custom_amount_state(
        bot_id=callback.bot.id,
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        receipt_id=receipt_id,
    )
    await _edit_callback_message(callback, prompt, reply_markup=None)


@admin_required
@error_handler
async def handle_c2c_approve(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_APPROVE_PREFIX)
    if receipt_id is None:
        await callback.answer('Invalid callback', show_alert=True)
        return

    await callback.answer()

    if _admin_chat_ok(callback):
        await execute_c2c_approve(callback, db, callback.from_user.id)
        return

    await execute_c2c_approve(callback, db, callback.from_user.id)


@admin_required
@error_handler
async def handle_c2c_reject(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_REJECT_PREFIX)
    if receipt_id is None:
        await callback.answer('Invalid callback', show_alert=True)
        return

    await callback.answer()
    await show_c2c_reject_menu(callback, db)


@admin_required
@error_handler
async def handle_c2c_reject_reason(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    parsed = _parse_reject_reason_callback(callback.data or '')
    if parsed is None:
        await callback.answer('Invalid callback', show_alert=True)
        return

    await callback.answer()
    await execute_c2c_reject(callback, db, callback.from_user.id, reason_key=parsed[1])


@admin_required
@error_handler
async def handle_c2c_restore_review(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_RESTORE_REVIEW_PREFIX)
    if receipt_id is None:
        await callback.answer('Invalid callback', show_alert=True)
        return

    await callback.answer()
    await restore_c2c_review_keyboard(callback, db)


@admin_required
@error_handler
async def handle_c2c_custom_amount_start(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX)
    if receipt_id is None:
        await callback.answer('Invalid callback', show_alert=True)
        return

    await callback.answer()
    await start_c2c_custom_amount(callback, db)


@admin_required
@error_handler
async def process_c2c_custom_amount(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
) -> None:
    data = await state.get_data()
    receipt_id = data.get('c2c_custom_receipt_id')
    if not receipt_id:
        await state.clear()
        return

    await _execute_c2c_custom_amount_input(
        message,
        db,
        receipt_id=int(receipt_id),
        language=db_user.language,
    )
    await state.clear()


@admin_required
@error_handler
async def handle_c2c_resolved(callback: types.CallbackQuery, db_user: User, db: AsyncSession) -> None:
    receipt_id = _parse_receipt_id(callback.data or '', C2C_CALLBACK_RESOLVED_PREFIX)
    if receipt_id is None:
        await callback.answer('Invalid callback', show_alert=True)
        return

    await on_c2c_resolved_tap(callback)


def register_admin_handlers(dp) -> None:
    from aiogram import Dispatcher

    assert isinstance(dp, Dispatcher)

    dp.callback_query.register(
        handle_c2c_approve,
        F.data.startswith(C2C_CALLBACK_APPROVE_PREFIX),
    )
    dp.callback_query.register(
        handle_c2c_reject_reason,
        F.data.startswith(C2C_CALLBACK_REJECT_REASON_PREFIX),
    )
    dp.callback_query.register(
        handle_c2c_reject,
        F.data.startswith(C2C_CALLBACK_REJECT_PREFIX),
    )
    dp.callback_query.register(
        handle_c2c_custom_amount_start,
        F.data.startswith(C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX),
    )
    dp.callback_query.register(
        handle_c2c_restore_review,
        F.data.startswith(C2C_CALLBACK_RESTORE_REVIEW_PREFIX),
    )
    dp.callback_query.register(
        handle_c2c_resolved,
        F.data.startswith(C2C_CALLBACK_RESOLVED_PREFIX),
    )
    dp.message.register(process_c2c_custom_amount, AdminStates.c2c_custom_amount)
